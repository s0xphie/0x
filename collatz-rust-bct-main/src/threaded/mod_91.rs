use std::{thread, sync::{Arc, Mutex}};

pub fn run() {
    let (q, r, w) = (String::from("100100100100100"), String::from("101110101011011101001110101110101110100000"), 3);
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
    if n_int > 100 {
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
        println!("{}", q);
        *q = m(q).to_string();
    }
}
