use std::env;

mod definitions {
    pub mod def;
}

mod threaded {
    pub mod mod_91;
    pub mod mod_100;
    pub mod incremental;
    pub mod mod_g;
}

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() == 1 {
        definitions::def::run();
    } else if args.len() > 5 {
        println!("Invalid number of arguments.");
        return;
    } else if &args[1] == "threaded" {
        match args.get(2).map(|x| x.as_str()) {
            None => {
                run_threaded("100");
            }
            Some("91") => {
                run_threaded("91");
            }
            Some("100") => {
                run_threaded("100");
            }
            Some("incremental") => {
                run_threaded("incremental");
            }
            Some("g") => {
                let initialize = args.get(3).map(|s| s.as_str()).unwrap_or("45");
                let t_seed = args.get(4).map(|s| s.as_str()).unwrap_or("255");
                threaded::mod_g::run(initialize, t_seed);
            }
            Some(arg) => {
                println!("Error: Unexpected argument '{}'", arg);
            }
        }
    } else {
        println!("Invalid arguments.");
    }
}

fn run_threaded(mod_to_run: &str) {
    match mod_to_run {
        "91" => threaded::mod_91::run(),
        "100" => threaded::mod_100::run(),
        "incremental" => threaded::incremental::run(),
        _ => println!("Invalid mod number."),
    }
}
