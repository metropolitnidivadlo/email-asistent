"""IMAP modified UTF-7 (RFC 3501, 5.1.3) pro názvy složek s diakritikou."""
import base64


def _b64_encode(chunk):
    raw = chunk.encode("utf-16-be")
    return base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")


def encode(name):
    out, buf = [], ""
    for ch in name:
        if 0x20 <= ord(ch) <= 0x7E:
            if buf:
                out.append("&" + _b64_encode(buf) + "-")
                buf = ""
            out.append("&-" if ch == "&" else ch)
        else:
            buf += ch
    if buf:
        out.append("&" + _b64_encode(buf) + "-")
    return "".join(out)


def decode(text):
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch != "&":
            out.append(ch)
            i += 1
            continue
        end = text.find("-", i)
        if end < 0:  # nevalidní, vrať jak je
            out.append(text[i:])
            break
        chunk = text[i + 1:end]
        if chunk == "":
            out.append("&")
        else:
            b64 = chunk.replace(",", "/")
            b64 += "=" * (-len(b64) % 4)
            out.append(base64.b64decode(b64).decode("utf-16-be"))
        i = end + 1
    return "".join(out)
