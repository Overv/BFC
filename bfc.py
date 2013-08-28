import sys
import os
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

class IncPtrNode(Node): pass
class DecPtrNode(Node): pass
class IncByteNode(Node): pass
class DecByteNode(Node): pass
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
# Linker
#

class Linker:
    # Byte size of ELF file structures (ELF header and program header)
    ELF_HDR_SIZE = 52
    PRO_HDR_SIZE = 32
    LOAD_ADDRESS = 0x08048000

    def __init__(self, code):
        self.code = code

    # Write 32-bit ELF executable with generated machine code
    def write(self, filename):
        with open(filename, 'w') as f:
            self.write_header(f)
            self.write_program_header(f, len(self.code))
            f.write(code)

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
    def write_program_header(self, f, code_size):
        file_size = self.ELF_HDR_SIZE + self.PRO_HDR_SIZE + code_size

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
    with open(sys.argv[1], 'r') as f:
        source = f.read()

    # Perform lexical analysis
    tokens = Lexer(source).tokenize()
    
    # Create abstract syntax tree
    try:
        tree = Parser(tokens).parse()
    except ParseException as e:
        sys.stderr.write('err: ' + str(e) + '\n')
        sys.exit(1)

    # Generate code
    # TODO
    code = '\xB8\x01\x00\x00\x00\xBB\x2A\x00\x00\x00\xCD\x80'

    # Write executable
    executable_name = os.path.splitext(sys.argv[1])[0]
    Linker(code).write(executable_name)