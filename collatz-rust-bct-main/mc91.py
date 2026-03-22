from time import sleep

def m(n):
    if n > 100: return n - 10
    return m(m(n + 11))

q, r, w = '100100100100100', '101110101011011101001110101110101110100000', 3

while q[w:]:
    if r[0] == '0': q = q[1:]
    else:
        r = r[1:] + r[0]
        if q[0] == '1': q += r[0]
    r = r[1:] + r[0]
    print(q)
    sleep(0.01)
    q = str(m(int(q)))
