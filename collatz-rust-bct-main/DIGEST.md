# Prototype Digest

This project is not one thing. It is a prototype family with a shared recurrence spine.

## Core Reading

- `slippy-main/slip.py` is the broad prototype.
- `src/definitions/def.rs` is the stripped BCT core.
- `src/threaded/mod_100.rs` is the same core with a threaded wrapper.
- `src/threaded/mod_91.rs` is the BCT core plus recursive numeric deformation.
- `src/threaded/incremental.rs` is generated-seed BCT.

## What The Family Really Is

The common center is a Bitwise Cyclic Tag style machine:

- `q` is the evolving word.
- `r` is the rotating control word.
- `w` is the stopping threshold.

The raw step is:

1. inspect the head of `r`
2. maybe drop the head of `q`
3. maybe append one bit from rotated `r` to `q`
4. rotate `r` again
5. print the current `q`

That exact shape is visible in:

- `src/definitions/def.rs`
- `src/threaded/mod_100.rs`
- `src/threaded/mod_91.rs`
- `slippy-main/slip.py`
- `mc91.py`

## Subsystems In `slippy`

`slippy-main/slip.py` is a stacked prototype with four phases.

### 1. Cellular Seed Phase

- prompts with `0xffffffff00000001/T:`
- reads an integer seed
- renders Rule 30 cellular automaton lines

This is the visible lattice / field-generation phase.

### 2. Fraction / Instruction Pointer Phase

- starts from `ip = 1 / 100000000000000000000000000000001`
- uses `commands = [3/2, 18446744073709551617, 16, 0, 3, 16]`
- repeatedly multiplies `ip` by the current command
- prints the fraction state as it moves

This is a Fractran-like control flow phase.

### 3. BCT + McCarthy-91 Phase

- starts from:
  - `q = 100100100100100`
  - `r = 101110101011011101001110101110101110100000`
  - `w = 3`
- performs the BCT recurrence
- after each printed step, replaces `q` with `m(int(q))`

In `slippy`, `m` is:

```py
def m(n):
    if n > 100:
        return n - 10
    return m(m(n + 11))
```

This is the recursively warped numeric stream phase.

### 4. Slash Phase

- starts from `I = "9/3/1"`
- uses `P = "/0."`
- repeatedly strips or rewrites slash-prefixed structure

This is the pointer / string-reduction phase.

## What The Rust App Preserves

### Default

`cargo run`

- preserves only the raw BCT recurrence
- no Rule 30
- no fraction/IP stage
- no slash stage
- no numeric warp

This is the cleanest expression of the core machine.

### Threaded 100

`cargo run -- threaded 100`

- same recurrence as default
- only wrapped in a thread
- behavior is effectively the same stream

### Threaded 91

`cargo run -- threaded 91`

- keeps the same BCT recurrence
- replaces `q` after each step with:

```rs
fn m(n: &str) -> String {
    let n_int: i128 = n.parse().unwrap();
    if n_int > 100 {
        (n_int - 10).to_string()
    } else {
        m(&(n_int + 11).to_string())
    }
}
```

Important note:

- this is not the full double-recursive McCarthy-91 form from `slippy`
- it is a simplified single-recursive deformation

So `threaded 91` is a partial extraction, not an exact preservation.

### Threaded Incremental

`cargo run -- threaded incremental`

This is the generated-seed variant.

It does three distinct things:

1. reads all `.txt` files in the current directory
2. interprets each file as a tiny state/rewrite machine
3. concatenates the generated strings into `q`

Then it runs a BCT-like loop with:

- `r = 1000000100000001`
- `w = 2`

and applies:

```rs
fn m(n: &str) -> String {
    let n_int: i128 = n.parse().unwrap();
    if n_int > 108 {
        (n_int - 10).to_string()
    } else {
        m(&(n_int + 11).to_string())
    }
}
```

It also reinterprets `q` numerically before printing:

- parses `q` in base 36
- prints the result in octal

So incremental is not just "BCT with input".
It is:

- rewrite-generated seed
- BCT recurrence
- recursive numeric deformation
- base-36 to octal projection

### Threaded G

`cargo run -- threaded g 45 255`

This is the stripped `config g` tail:

- no Rule 30 prelude
- no fraction/IP print stream
- no slash layer
- just the BCT-derived tail projected into hex-address form

Current verified output:

- `0xe337fcad74c14b3d15598cf2c`
- `0x250bd`

So this mode preserves the bare Rust stream style while still carrying the `config g` address projection.

## The Role Of `1.1`

`1.1` is not the main semantic center of the project.

What is primary:

- Bitwise Cyclic Tag / Acyclic Tag style recurrence
- Rule 30 cellular generation
- fraction/IP control
- slash reduction

What `1.1` influences:

- the generated-seed / incremental path
- the idea that small text programs can synthesize `q`

So `1.1` is auxiliary here, not foundational.

## The Role Of `slippy`

`slippy` is the better prototype map than the Rust app.

Why:

- it still contains the layered design
- it shows how field, control, recurrence, and reduction were originally chained
- it makes the lineage visible:
  - cellular automaton
  - Fractran-like pointer evolution
  - BCT / Acyclic Tag
  - McCarthy-91 recursion
  - slash language

The Rust tool is best understood as:

- a narrowed extraction of the BCT-centered slice
- plus one generated-seed experiment

## `slippy` Config Taxonomy

The `slippy-main/configs/` directory is not one coherent API.
It is a set of branch experiments around the main prototype.

### `configs/a`

- closest to the full `slippy` stack
- takes ternary-ish slash input
- converts that input through base-3 / hex / binary
- runs Rule 30
- runs fraction/IP
- runs warped BCT
- finishes in slash reduction

This is the best standalone config if we want a miniature of the whole prototype.

Important warning:

- it can fall into very long or effectively infinite slash reductions
- this matches the warning in `configs/slash.md`

### `configs/b`

- parameterizes the first command in the fraction/IP phase
- still runs Rule 30
- still runs warped BCT
- still ends in slash reduction
- contains a lot of literal `111...` separators and looks more like a hacked lab notebook than a stable module

This is an "input-perturbed slippy" branch.

### `configs/c`

- similar to `b`
- computes differences between large command numerators
- prints those deltas before continuing

This branch seems focused on arithmetic inspection of the command structure.

### `configs/d`

- computes a Rule 30-derived denominator
- builds a new fraction/IP state from it
- shifts toward hexadecimal address generation
- base64-encodes the evolving `q`
- multiplies the resulting integer by `0xffffffff00000001`

This is an address-emission branch.

### `configs/e`

- very close to `d`
- prints Rule 30 output
- runs a fraction/IP prelude
- then emits long hexadecimal addresses derived from the warped `q`

This is the cleanest "address stream" branch I tested.

### `configs/f`

- introduces a separate arithmetic function `fb`
- computes a sequence with `phi`, `beta`, and divisibility structure
- mixes in fizz-buzz style logic
- keeps a set of unique hex addresses
- mutates recurrence behavior when addresses repeat
- writes output toward `output.txt`

This is the most overloaded branch.
It is less a config and more a composite research notebook.

### `configs/g`

- the smallest address-oriented branch
- parameterizes the first fraction/IP command
- prints Rule 30
- runs a shorter fraction/IP sequence
- uses a smaller BCT seed:
  - `q = 100000001`
  - `r = 900001`
  - `w = 3`
- emits a very short hex-address tail

This is a compact recurrence-to-address prototype.

### `slash.py`

- dedicated slash-oriented branch
- takes slash input directly
- still mixes in Rule 30, fraction/IP, and warped BCT

This is best understood as "slippy with slash as the main visible entry surface."

### `ternary_digit_pointer.py`

- the lightest branch
- converts ternary-ish user input into a binary seed
- runs a short Rule 30 display
- finishes with slash reduction
- does not include the full fraction/IP or BCT stack

This is a front-end / pointer toy more than a full `slippy`.

## Related Prototype Surface

`slippy-main/soh10fffe.py` is another separate seam:

- bit-tape based
- binary logic operations
- explicit input/output bit buffers
- restart opcode `|`

It belongs to the same experimental family, but it is not part of the BCT core.

The compiled sample is:

- `slippy-main/Slip.soh10fffe`

Running it through the interpreter produces:

- a warning about uneven output-bit buffering
- a long repeated byte-pattern style output

So this seam is genuinely executable, but it is much closer to a raw tape machine than to the layered `slippy` prototype.

## Commands Verified

- `cargo run --quiet`
- `cargo run --quiet -- threaded 91`
- `printf '255\n\n' | python3 slippy-main/slip.py`
- `printf '45\n255\n' | python3 slippy-main/configs/g/config.py`
- `printf '255\n255\n' | python3 slippy-main/configs/e/config.py`
- `printf 'Slip.soh10fffe\n' | python3 soh10fffe.py`

Observed behavior matched the code structure:

- `slippy` really does run Rule 30 -> fraction/IP -> warped BCT -> slash
- default Rust really is raw BCT
- `91` really is warped BCT
- `configs/e` and `configs/g` are real address-emission branches
- `soh10fffe` is a live tape/interpreter seam
- `configs/a` can explode into a huge slash loop from tiny input

## Best Use Inside Supersingularity

If we bridge this family into `supersingularity`, the cleanest mapping is:

- Rule 30 phase -> field / lattice perturbation source
- fraction/IP phase -> control / continuation modulation
- BCT phase -> deterministic symbolic recurrence stream
- recursive warp phase -> nonlinear continuation pressure
- slash phase -> pointer / reduction / address pruning

So the right digestion is:

- `slippy` is the layered prototype
- Rust is the BCT extractor
- `incremental` is the generated-seed variant
- `1.1` is a minor seed-synthesis seam, not the heart
