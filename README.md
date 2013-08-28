BFC
===

BFC is an ahead-of-time compiler for
[brainfuck](http://en.wikipedia.org/wiki/Brainfuck). It takes a brainfuck source
file and outputs native code in the form of a 32-bit ELF executable. The
executable only depends on Linux syscalls, not the C library or anything else.
This is basically as fast as unoptimized brainfuck code is going to get.

The output program allocates 1 MB (1048576 cells) of memory on the stack for the
tape. That is more than enough, even for complex programs like the [mandelbrot
renderer](http://esoteric.sange.fi/brainfuck/utils/mandelbrot/mandelbrot.b) by
Erik Bosman. Because the stack grows downwards, the increase and decrease
pointer operations are reversed in the output code.

Although a language like C is generally more suitable for low-level development
like this, I decided to implement it in Python because it makes the code simply
more readable and easy to understand. Additionally, it removes frustrations like
having to implement file reading code for the 1000th time. The source should be
valid Python 2.7 and Python 3.x code.

Usage
-----

Prepare a brainfuck source file, like `tests/hello.bf` and invoke the compiler
by running:

    ./bfc.py hello.bf

If the file could be read and correctly parsed, then an executable named `hello`
will be produced in the same directory.

Details
-------

Since this project simultaneously serves as a learning sample for basic compiler
architectures, it is set up like a regular compiler. The input source goes
through the

- Lexing
- Parsing
- Compiling
- Linking

passes to result in an output executable. The lexer simply discards all
characters that are not part of the brainfuck language and turns the characters
into tokens, implemented as child classes of `Token`. The parser is a recursive
descent parser and basically only exists for loops. It's included for
completeness more than anything else, although the tree it creates does help a
bit with code generation logic.

The parser is implemented using the recursive-descent approach, according to the
following LL(1) grammar in EBNF form:

    program  = { command | loop }
    command  = ">" | "<" | "+" | "-" | "." | ","
    loop     = "[", { command | loop }, "]

Each node in the tree outputs one or two
instructions that are written to a byte buffer. Jumps are written with the
correct addresses corresponding to loop beginnings. The final pass creates a
bare-bones ELF file and puts the program in an executable section in memory.

There are no checks at runtime, so if you mess up the program, it will happily
write or read memory where it shouldn't. Because the behaviour of brainfuck is
rather hard to predict, the only solution would be to add bounds checks to every
read and write, but all these branches would significantly impact performance.

The code generated for each token is listed below. Input and output is handled
by the read and write syscalls on Linux. They are called using interrupt `0x80`.
The exit syscall is used to end the program.

**>**
```nasm
dec esp
```

**<**
```nasm
inc esp
```

**+**
```nasm
inc [esp]
```

**-**
```nasm
dec [esp]
```

**.**
```nasm
mov eax, 0x4 ; write
mov ebx, 0x1 ; stdout
mov ecx, esp
mov edx, 0x1 ; write 1 byte at pointer
int 0x80
```

**,**
```nasm
mov eax, 0x3 ; read
mov ebx, 0x0 ; stdin
mov ecx, esp
mov edx, 0x1 ; read 1 byte to pointer
int 0x80
```

**[**
```nasm
loop:
    cmp [esp], 0
    je loop_end
```

**]**
```nasm
    jmp loop
loop_end:
```

**EOF**
```nasm
mov eax, 1 ; exit
mov ebx, 0 ; EXIT_SUCCESS (= 0)
int 0x80
```

It may be an interesting experiment to mark the code section itself as writable
and allow for self-modifying code that way.

License
-------

BFC is licensed under the MIT license, of which the terms are outlined in the
`LICENSE` file.