pub fn run() {
    let mut q = String::from("100100100100100");
    let mut r = String::from("101110101011011101001110101110101110100000");
    let w = 3;

    while q.len() > w {
        if r.chars().next() == Some('0') {
            q = q.chars().skip(1).collect();
        } else {
            r = r.chars().skip(1).chain(r.chars().take(1)).collect();
            if q.chars().next() == Some('1') {
                q.push(r.chars().next().unwrap());
            }
        }
        r = r.chars().skip(1).chain(r.chars().take(1)).collect();
        println!("{}", q);
    }
}