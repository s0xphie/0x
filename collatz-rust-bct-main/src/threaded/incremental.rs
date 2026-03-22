
use regex::Regex;
use std::fs;
use std::io::{self, BufRead};
use std::{thread, sync::{Arc, Mutex}};

fn interpret_program(prog: Vec<&str>, debug: bool) -> String {
    #[allow(unused_assignments)]
    let mut buffer = String::new();

    // Set buffer to start
    let cur_state: Vec<&str> = prog[0].split('|').collect();

    // If starting buffer is empty, read from stdin
    if cur_state.len() == 1 {
        println!("Enter starting buffer:");
        let mut temp = String::new();
        io::stdin().lock().read_line(&mut temp).expect("Failed to read line");
        buffer = temp.trim().to_string();
    } else {
        buffer = cur_state[1].to_string();
    }

    // Set statement to after start
    let mut state_num = 2;
    while state_num <= prog.len() {
        // Get the current state
        let cur_state: Vec<&str> = prog[state_num - 1].split('|').collect();

        // Check for Halt
        if cur_state[1].to_lowercase() == "halt" {
            break;
        } else {
            let needle = Regex::new(&regex::escape(cur_state[1])).unwrap();
            if needle.is_match(&buffer) {
                if debug {
                    print!(
                        "{}: {} ---> {} == ",
                        state_num,
                        cur_state[1],
                        cur_state[2]
                    );
                }
                // Replace needle with replacement string
                buffer = needle.replace_all(&buffer, cur_state[2]).to_string();
                state_num = cur_state[3].parse().unwrap();
            } else {
                if debug {
                    print!("{}: {} not found. == ", state_num, cur_state[1]);
                }
                state_num = cur_state[4].parse().unwrap();
            }
        }

        // If debug is turned on, print buffer every time
        if debug {
            println!("{}", buffer);
        }
    }

        buffer
}

fn generate_q() -> String {
    let current_dir = std::env::current_dir().expect("Failed to get current directory");

    let mut files: Vec<_> = fs::read_dir(current_dir)
        .expect("Failed to read directory")
        .filter_map(Result::ok)
        .map(|dir_entry| dir_entry.path())
        .filter(|path| {
            if let Some(extension) = path.extension() {
                if let Some(ext) = extension.to_str() {
                    return ext.to_lowercase() == "txt";
                }
            }
            false
        })
        .collect();

    files.sort();

    let mut generated_result = String::new(); // Placeholder for the generated value

    for file in files {
        let file_content = fs::read_to_string(&file).expect("Failed to read file");
        let prog: Vec<&str> = file_content.lines().collect();
        let debug = false; // Set debug mode if needed

        generated_result.push_str(&interpret_program(prog, debug)); // Append the generated result
        print!("{}", generated_result);
    }

    generated_result // Return the generated result
}

pub fn run() {
    let q = generate_q(); // Get the generated value as a string

    let r = String::from("1000000100000001");
    let w = 2;
    let stop_event = Arc::new(Mutex::new(false));
    let (q_arc, r_arc) = (Arc::new(Mutex::new(q)), Arc::new(Mutex::new(r)));
    let (q_arc_clone, r_arc_clone, stop_event_clone) = (q_arc.clone(), r_arc.clone(), stop_event.clone());

    let handle = thread::spawn(move || {
        perform_bitwise_cyclic_tag(&mut q_arc_clone.lock().unwrap(), &mut r_arc_clone.lock().unwrap(), w, stop_event_clone);
    });

    handle.join().unwrap();
}

fn m(n: &str) -> String {
    let n_int: i128 = n.parse().unwrap();
    if n_int > 108 {
        (n_int - 10).to_string()
    } else {
        m(&(n_int + 11).to_string())
    }
}

fn perform_bitwise_cyclic_tag(q: &mut String, r: &mut String, w: usize, stop_event: Arc<Mutex<bool>>) {
    while q.len() > w && !*stop_event.lock().unwrap() {
        if r.chars().next() == Some('0') {
            q.remove(0);
        } else {
            let first_char = r.remove(0);
            r.push(first_char);
            if q.chars().next() == Some('1') {
                q.push(r.chars().next().unwrap());
            }
        }
        let first_char_r = r.remove(0);
        r.push(first_char_r);

        if let Ok(integer_value) = i128::from_str_radix(&q, 36) {
            let value = format!("{:o}", integer_value);
            println!("{}", value);
        }

        *q = m(q).to_string();
    }
}

