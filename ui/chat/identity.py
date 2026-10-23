"""Rendered mesaj kimliği + row güncelleme sunum yardımcıları (Faz 4C-3A).

Stateless; yalnız rendered widget'lar üzerinde çalışır. Domain/storage/DB/
network/thread/after/queue/async YOKTUR. State sahipliği çağırandadır.
"""
import tkinter as tk


def find_row_by_mid(rows, mid):
    """mid → ilk eşleşen row (mevcut doğrusal tarama semantiği)."""
    if not mid:
        return None
    for w in rows:
        if getattr(w, "_mid", "") == mid:
            return w
    return None


def find_last_message_row(rows, mine):
    """Bu sohbetteki son (benim/gelen), retracted olmayan mid'li satır."""
    for w in reversed(rows):
        if (getattr(w, "_is_me", False) == mine
                and not getattr(w, "_retracted", False)
                and getattr(w, "_mid", "")):
            return w
    return None


def update_bubble_text(row, new_text, *, edited=False, retracted=False,
                       formatter, theme):
    """Bir mesaj balonunun metin içeriğini güncelle (saf UI)."""
    text = new_text if retracted else (f"{new_text}  ✏" if edited else new_text)
    # 1) _append'in bıraktığı seçilebilir gövde (tercih edilen yol);
    #    düzeltme markdown'ı korur, metin seçilebilir kalır
    box = getattr(row, "_body_text", None)
    if box is not None:
        try:
            if box.winfo_exists():
                if retracted:
                    box.set_content(text, fg=theme["FG_DIM"],
                                    font=(theme["FONT"], 9, "italic"))
                else:
                    parts = list(formatter(new_text))
                    if edited:
                        parts.append(("  ✏", None))
                    box.set_content(parts)
                return
        except Exception:
            pass
    # 2) Geriye dönük: eski balonlar için sezgisel tarama
    for child in row.winfo_children():
        if isinstance(child, tk.Frame):
            for sub in child.winfo_children():
                if (isinstance(sub, tk.Label) and sub.cget("font")
                        and "10" in str(sub.cget("font"))):
                    if retracted:
                        sub.config(text=text, fg=theme["FG_DIM"],
                                   font=(theme["FONT"], 9, "italic"))
                    else:
                        sub.config(text=text)
                    return


def apply_correction_to_row(row, new_body, *, formatter, theme):
    """Rendered row'a correction görsel mutasyonu (identity/state yazmaz)."""
    row._body = new_body
    row._edited = True
    update_bubble_text(row, new_body, edited=True, formatter=formatter,
                       theme=theme)


def apply_retraction_to_row(row, body, *, formatter, theme, clear_reactions):
    """Rendered row'a retraction görsel mutasyonu (state maps'e dokunmaz)."""
    row._body = body
    row._retracted = True
    update_bubble_text(row, body, retracted=True, formatter=formatter,
                       theme=theme)
    clear_reactions(row)


def scroll_to_row(canvas, msg_frame, row, offset=60):
    """Row'u görünür alana kaydır (minimal; canvas/msg_frame caller'dan)."""
    try:
        msg_frame.update_idletasks()
        total = max(1, msg_frame.winfo_height())
        y = row.winfo_y()
        canvas.yview_moveto(max(0.0, min(1.0, (y - offset) / total)))
    except Exception:
        pass
