#!/usr/bin/python

import sys
import os
import stat
import struct

#
# Types of lexical tokens
#

class Token:
    def __repr__(self):
        return self.__class__.__name__

class IncPtrToken(Token): pass
class DecPtrToken(Token): pass
class IncByteToken(Token): pass
class DecByteToken(Token): pass
class OutputToken(Token): pass
class InputToken(Token): pass
class LoopStartToken(Token): pass
class LoopEndToken(Token): pass

#
# Lexer
#

class Lexer:
    def __init__(self, source):
        self.source = source

    # Perform lexical analysis and return the tokens
    def tokenize(self):
        tokens = []

        # Turn all commands into tokens and discard the rest as comments
        for char in self.source:
            if char == '>':   tokens.append(IncPtrToken())
            elif char == '<': tokens.append(DecPtrToken())
            elif char == '+': tokens.append(IncByteToken())
            elif char == '-': tokens.append(DecByteToken())
            elif char == '.': tokens.append(OutputToken())
            elif char == ',': tokens.append(InputToken())
            elif char == '[': tokens.append(LoopStartToken())
            elif char == ']': tokens.append(LoopEndToken())

        return tokens

#
# Types of AST nodes
#

class Node: pass

# Used by optimizer to merge certain nodes with a repeat count
class MergeableNode(Node):
    def __init__(self, count = 1):
        self.count = count

    def __eq__(self, other):
        return isinstance(other, self.__class__)

class IncPtrNode(MergeableNode): pass
class DecPtrNode(MergeableNode): pass
class IncByteNode(MergeableNode): pass
class DecByteNode(MergeableNode): pass

class OutputNode(Node): pass
class InputNode(Node): pass

class ProgramNode(Node):
    def __init__(self, nodes):
        self.nodes = nodes

class LoopNode(Node):
    def __init__(self, nodes):
        self.nodes = nodes

#
# Parse exception
#

class ParseException(Exception):
    pass

#
# Recursive-descent parser (see formal grammar)
#

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    # Returns True if all tokens have been read
    def eof(self):
        return self.index == len(self.tokens)

    # Returns the next token
    def peek(self):
        if self.eof():
            raise ParseException('unexpected end of file')

        return self.tokens[self.index]

    # Reads the next token
    def read(self):
        tok = self.peek()
        self.index += 1
        return tok

    # Reads the next token and checks if it's of the expected type
    def expect(self, token_type):
        tok = self.read()
        
        if isinstance(tok, token_type):
            return tok
        else:
            raise ParseException('unexpected token ' + str(tok))

    # Parse input tokens into an AST with program root node
    def parse(self):
        return self.parse_program()

    # Parse program node (sequence of commands and loops)
    def parse_program(self):
        nodes = []

        # Repeatedly parse either a loop or a command until EOF is reached
        while not self.eof():
            if isinstance(self.peek(), LoopStartToken):
                nodes.append(self.parse_loop())
            else:
                nodes.append(self.parse_command())

        return ProgramNode(nodes)

    # Parse a single command (e.g. increase pointer or output byte)
    def parse_command(self):
        tok = self.read()

        if isinstance(tok, IncPtrToken): return IncPtrNode()
        elif isinstance(tok, DecPtrToken): return DecPtrNode()
        elif isinstance(tok, IncByteToken): return IncByteNode()
        elif isinstance(tok, DecByteToken): return DecByteNode()
        elif isinstance(tok, OutputToken): return OutputNode()
        elif isinstance(tok, InputToken): return InputNode()
        else: raise ParseException('unexpected token ' + str(tok))

    # Parse a loop
    def parse_loop(self):
        nodes = []

        # Loops start with [
        self.expect(LoopStartToken)

        # Parse loop body (sequence of commands and nested loops)
        while not isinstance(self.peek(), LoopEndToken):
            if isinstance(self.peek(), LoopStartToken):
                nodes.append(self.parse_loop())
            else:
                nodes.append(self.parse_command())

        # Loops end with ]
        self.expect(LoopEndToken)

        return LoopNode(nodes)

#
# Optimizer
#

class Optimizer:
    def __init__(self, tree):
        self.tree = tree

    def optimize(self, node = None):
        if node == None:
            # Start with optimization at root node
            return self.optimize(self.tree)
        elif isinstance(node, ProgramNode) or isinstance(node, LoopNode):
            # Optimize nodes within root and loop nodes
            nodes = []

            last_node = None
            repeats = 0

            for n in node.nodes:
                n = self.optimize(n)

                # Limit optimization to 255 repetitions (very rare anyway)
                if isinstance(n, MergeableNode) and n == last_node and last_node.count < 255:
                    last_node.count += 1
                else:
                    nodes.append(n)
                    last_node = n

            if isinstance(node, ProgramNode):
                return ProgramNode(nodes)
            else:
                return LoopNode(nodes)
        else:
            # Other nodes don't contain any nodes to optimize
            return node

#
# Code generator
#

class CodeGenerator:
    # x86 reference (addressing modes and opcodes)
    # http://ref.x86asm.net/coder32-abc.html

    # Instructions
    MOV_REG_IMM = 0xB8
    MOV_REG_REG = 0x89
    XOR = 0x31
    ADDSUB = 0x83 # Opcode extension determines add/sub
    INC = 0x40
    DEC = 0x48
    INT = 0xCD
    STD = 0xFD
    REP = 0xF3
    STOSD = 0xAB
    JMP = 0xE9
    JE = '\x0F\x84'

    # Addressing modes
    MOD_RR = 0b11 # register/register

    # Registers
    EAX = 0b000
    ECX = 0b001
    EDX = 0b010
    EBX = 0b011
    ESP = 0b100
    EBP = 0b101
    ESI = 0b110
    EDI = 0b111

    # Interrupts
    SYSCALL = 0x80

    def __init__(self, tree):
        self.tree = tree

    # Generate machine code for given node
    def generate(self, node = None):
        code = ''

        if node == None:
            # Start with code generation at the root node
            return self.generate(self.tree)
        elif isinstance(node, ProgramNode):
            # Initialize 1 MB on the stack to zero
            code += self.xor(self.EAX, self.EAX)
            code += self.mov_ri(self.ECX, 0x40000)
            code += self.mov_rr(self.EDI, self.ESP)
            code += self.std()
            code += self.rep_stos()

            # Generate code for all commands in the program
            for node in node.nodes:
                code += self.generate(node)

            # Call exit syscall to end the program
            code += self.xor(self.EAX, self.EAX)
            code += self.inc_reg(self.EAX)
            code += self.xor(self.EBX, self.EBX)
            code += self.int(self.SYSCALL)
        elif isinstance(node, LoopNode):
            # First generate code for loop body to calculate relative jumps
            body_code = ''

            for node in node.nodes:
                body_code += self.generate(node)

            # Add loop prelude with conditional jump to end of loop
            code += self.cmp_esp_byte(0)
            code += self.je(len(body_code) + 5)

            # Append the loop body code
            code += body_code

            # And finally add the unconditional jump back to the beginning
            code += self.jmp(-len(body_code) - 15)
        elif isinstance(node, IncPtrNode):
            # Move down stack
            if node.count == 1:
                code += self.dec_reg(self.ESP)
            else:
                code += self.sub_reg(self.ESP, node.count)  
        elif isinstance(node, DecPtrNode):
            # Move up stack
            if node.count == 1:
                code += self.inc_reg(self.ESP)
            else:
                code += self.add_reg(self.ESP, node.count)
        elif isinstance(node, IncByteNode):
            # Increment the byte at the stack pointer
            if node.count == 1:
                code += self.inc_esp_byte()
            else:
                code += self.add_esp_byte(node.count)
        elif isinstance(node, DecByteNode):
            # Decrement the byte at the stack pointer
            if node.count == 1:
                code += self.dec_esp_byte()
            else:
                code += self.sub_esp_byte(node.count)
        elif isinstance(node, OutputNode):
            # Call the write syscall with the stack pointer
            code += self.mov_ri(self.EAX, 0x4)
            code += self.mov_ri(self.EBX, 0x1)
            code += self.mov_rr(self.ECX, self.ESP)
            code += self.mov_ri(self.EDX, 0x1)
            code += self.int(self.SYSCALL)
        elif isinstance(node, InputNode):
            # Call the read syscall with the stack pointer
            code += self.mov_ri(self.EAX, 0x3)
            code += self.mov_ri(self.EBX, 0x0)
            code += self.mov_rr(self.ECX, self.ESP)
            code += self.mov_ri(self.EDX, 0x1)
            code += self.int(self.SYSCALL)

        return code

    # Assembler functions
    def mov_ri(self, dst, val):
        return chr(self.MOV_REG_IMM + dst) + struct.pack('<I', val)

    def mov_rr(self, dst, src):
        return chr(self.MOV_REG_REG) + chr(dst | src << 3 | self.MOD_RR << 6)

    def xor(self, dst, src):
        return chr(self.XOR) + chr(dst | src << 3 | self.MOD_RR << 6)

    def add_reg(self, dst, val):
        # Add 8-bit value to 32-bit register (opcode extension = 0)
        return chr(self.ADDSUB) + chr(dst | self.MOD_RR << 6) + chr(val)

    def sub_reg(self, dst, val):
        # Subtract 8-bit value from 32-bit register (opcode extension = 5)
        return chr(self.ADDSUB) + chr(dst | 5 << 3 | self.MOD_RR << 6) + chr(val)

    def add_esp_byte(self, val):
        return '\x80\x04\x24' + chr(val)

    def sub_esp_byte(self, val):
        return '\x80\x2C\x24' + chr(val)

    def inc_reg(self, reg):
        return chr(self.INC + reg)

    def dec_reg(self, reg):
        return chr(self.DEC + reg)

    def inc_esp_byte(self):
        return '\xFE\x04\x24' # inc byte [esp]

    def dec_esp_byte(self):
        return '\xFE\x0C\x24' # dec byte [esp]

    def cmp_esp_byte(self, val):
        return '\x80\x3C\x24' + chr(val) # cmp byte [esp], val

    def jmp(self, rel):
        return chr(self.JMP) + struct.pack('<i', rel)

    def je(self, rel):
        return self.JE + struct.pack('<i', rel)

    def int(self, name):
        return chr(self.INT) + chr(name)

    def std(self):
        return chr(self.STD)

    def rep_stos(self):
        return chr(self.REP) + chr(self.STOSD)

#
# Linker
#

class Linker:
    # ELF details
    ELF_HDR_SIZE = 52
    PRO_HDR_SIZE = 32
    LOAD_ADDRESS = 0x08048000

    def __init__(self, code):
        self.code = code

    # Write 32-bit ELF executable with generated machine code
    def write(self, filename):
        with open(filename, 'wb') as f:
            self.write_header(f)
            self.write_program_header(f)
            f.write(code)

        # Add executable permission
        perms = stat.S_IMODE(os.stat(filename).st_mode)
        os.chmod(filename, perms | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Write ELF header
    # http://www.sco.com/developers/gabi/1998-04-29/ch4.eheader.html
    def write_header(self, f):
        entry_point = self.LOAD_ADDRESS + self.ELF_HDR_SIZE + self.PRO_HDR_SIZE

        f.write('\x7FELF') # File identifier
        f.write('\x01') # 32-bit
        f.write('\x01') # Little-endian (x86)
        f.write('\x00') # Current header version
        f.write('\x00') # Unix System V ABI
        f.write('\x00')
        f.write('\x00' * 7) # Padding to 16 bytes

        f.write(struct.pack('<H', 2)) # Executable file
        f.write(struct.pack('<H', 3)) # Intel 80386
        f.write(struct.pack('<I', 1)) # Current object file version
        f.write(struct.pack('<I', entry_point)) # Entry point
        f.write(struct.pack('<I', self.ELF_HDR_SIZE)) # Program header offset
        f.write(struct.pack('<I', 0)) # Section header offset (none)
        f.write(struct.pack('<I', 0)) # Processor flags (none)
        f.write(struct.pack('<H', self.ELF_HDR_SIZE)) # ELF header size
        f.write(struct.pack('<H', self.PRO_HDR_SIZE)) # Program header size
        f.write(struct.pack('<H', 1)) # Program header table entries (1)
        f.write(struct.pack('<H', 0)) # TODO: Section header size (none)
        f.write(struct.pack('<H', 0)) # Section header table entries (none)
        f.write(struct.pack('<H', 0)) # String table entry index (none)

    # Write single program header entry
    # It is common to simply load the entire executable into memory.
    # http://www.sco.com/developers/gabi/1998-04-29/ch5.pheader.html
    def write_program_header(self, f):
        file_size = self.ELF_HDR_SIZE + self.PRO_HDR_SIZE + len(self.code)

        f.write(struct.pack('<I', 1)) # Load section into memory
        f.write(struct.pack('<I', 0)) # File offset
        f.write(struct.pack('<I', self.LOAD_ADDRESS)) # Virtual memory address
        f.write(struct.pack('<I', self.LOAD_ADDRESS)) # Physical memory address
        f.write(struct.pack('<I', file_size)) # File image size
        f.write(struct.pack('<I', file_size)) # Memory image size
        f.write(struct.pack('<I', 0x1 | 0x4)) # Execute and read flags
        f.write(struct.pack('<I', 0x1000)) # Alignment (4 KB)

#
# Main program
#

if __name__ == '__main__':

    # Check if a source file was specified
    if len(sys.argv) != 2:
        sys.stderr.write('usage: bfc.py <program.bf>\n')
        sys.exit(1)

    # Read brainfuck source
    try:
        with open(sys.argv[1], 'r') as f:
            source = f.read()
    except IOError:
        sys.stderr.write('err: could not read input file\n')
        sys.exit(1)

    # Perform lexical analysis
    tokens = Lexer(source).tokenize()
    
    # Create abstract syntax tree
    try:
        tree = Parser(tokens).parse()
    except ParseException as e:
        sys.stderr.write('err: ' + str(e) + '\n')
        sys.exit(1)

    # Optimize
    tree = Optimizer(tree).optimize()

    # Generate code
    code = CodeGenerator(tree).generate()

    # Write executable
    executable_name = os.path.splitext(sys.argv[1])[0]
    Linker(code).write(executable_name)