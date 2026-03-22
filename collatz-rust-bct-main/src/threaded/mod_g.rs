use num_bigint::BigUint;
use num_traits::Num;

pub fn run(_initialize: &str, _t_seed: &str) {
    let mut q = String::from("100100100100100");
    let mut r = String::from("101110101011011101001110101110101110100000");
    let w = 3;

    while q.len() > w {
        if r.chars().next() == Some('0') {
            q.remove(0);
        } else {
            rotate_left(&mut r);
            if q.chars().next() == Some('1') {
                let next = r.chars().next().unwrap();
                q.push(next);
            }
        }

        rotate_left(&mut r);
        q = mc91(q.parse::<u128>().unwrap()).to_string();
        println!("{}", project_hex_address(&q));
    }
}

fn rotate_left(text: &mut String) {
    let first = text.remove(0);
    text.push(first);
}

fn mc91(n: u128) -> u128 {
    if n > 100 {
        n - 10
    } else {
        mc91(mc91(n + 11))
    }
}

fn project_hex_address(q: &str) -> String {
    let hex_payload = q
        .as_bytes()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();

    let hex_address = BigUint::from_str_radix(&hex_payload, 36).unwrap();
    format!("0x{}", hex_address.to_str_radix(16))
}
