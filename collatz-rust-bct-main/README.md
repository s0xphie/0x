# Collatz Rust BCT

This is a Rust application that generates a Collatz-like sequence based on Bitwise Cyclic Tag
https://esolangs.org/wiki/Bitwise_Cyclic_Tag


## Prerequisites

To build and run this application, you need to have Rust and Cargo installed on your system. If you don't have them already, you can install Rust by following the instructions at [Rust's official website](https://www.rust-lang.org/learn/get-started).

## Getting Started

1. Clone or download this repository to your local machine.

2. Navigate to the project directory using your terminal.

3. Build and run the application using Cargo: `cargo run`

3. For threaded mode: `cargo run threaded`

4. Recursive "mc91" function: `cargo run threaded 91`

5. Incremental mode:<br>
This mode utilizes a 1.1 lang interpereter to write the value of q incrementally using the !!.txt files<br>
!.txt files are weights, and you can reconfigure them, copying them multiple times into the directory<br>
will add that unit to the bitwise cyclic tag system.

```
cargo run threaded incremental
``` 

    

The program will compile, execute, and display the output in your terminal.

based on python code from this model:<br>
https://www.youtube.com/watch?v=EsuRs7plG88<br>
1.1 Esolangs: https://esolangs.org/wiki/1.1<br> 
1.1 interpereter: https://github.com/Sxakalo/1.1-Lang<br>

mc91.py is same concept with mc91 function in python
