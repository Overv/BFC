import sys

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
        self.index = self.index + 1
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