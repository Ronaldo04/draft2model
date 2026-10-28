"""309: diferencia por píxel entre dos PNG del mismo tamaño: caja, píxeles distintos y filas afectadas (en px y pt)."""
import sys, json
import pymupdf


def comparar(a_path, b_path, umbral=48, escala_pt=595 / 1058):
    a, b = pymupdf.Pixmap(a_path), pymupdf.Pixmap(b_path)
    assert (a.width, a.height, a.n) == (b.width, b.height, b.n)
    sa, sb, n, w = a.samples, b.samples, a.n, a.width
    filas = {}
    for y in range(a.height):
        base = y * a.stride
        for x in range(w):
            i = base + x * n
            if max(abs(sa[i+k] - sb[i+k]) for k in range(min(n, 3))) > umbral:
                f = filas.setdefault(y, [x, x, 0]); f[0] = min(f[0], x); f[1] = max(f[1], x); f[2] += 1
    if not filas:
        return {"pixeles_distintos": 0}
    ys = sorted(filas); bandas = []; ini = ys[0]; prev = ys[0]
    for y in ys[1:] + [None]:
        if y is None or y > prev + 3:
            xs = [filas[k] for k in range(ini, prev + 1) if k in filas]
            bandas.append({"y_px": [ini, prev], "x_px": [min(v[0] for v in xs), max(v[1] for v in xs)], "pixeles": sum(v[2] for v in xs),
                           "y_pt": [round(ini * escala_pt, 1), round(prev * escala_pt, 1)], "x_pt": [round(min(v[0] for v in xs) * escala_pt, 1), round(max(v[1] for v in xs) * escala_pt, 1)]})
            if y is not None: ini = y
        if y is not None: prev = y
    return {"pixeles_distintos": sum(v[2] for v in filas.values()), "bandas": bandas}


if __name__ == "__main__":
    print(json.dumps(comparar(sys.argv[1], sys.argv[2]), indent=1))
