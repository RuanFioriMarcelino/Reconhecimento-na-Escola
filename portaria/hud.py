import unicodedata

import cv2


def _ascii(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _draw_corner_box(frame, x: int, y: int, w: int, h: int, color: tuple[int, int, int], thickness: int = 2):
    cl = max(14, min(w, h) // 4)
    # Superior esquerdo
    cv2.line(frame, (x, y), (x + cl, y), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x, y), (x, y + cl), color, thickness, cv2.LINE_AA)
    # Superior direito
    cv2.line(frame, (x + w, y), (x + w - cl, y), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x + w, y), (x + w, y + cl), color, thickness, cv2.LINE_AA)
    # Inferior esquerdo
    cv2.line(frame, (x, y + h), (x + cl, y + h), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x, y + h), (x, y + h - cl), color, thickness, cv2.LINE_AA)
    # Inferior direito
    cv2.line(frame, (x + w, y + h), (x + w - cl, y + h), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - cl), color, thickness, cv2.LINE_AA)


class HudRenderer:
    """HUD passivo de alta legibilidade sem bloqueio visual ou pedidos de autorização."""

    def render(self, frame, tracks: list[dict], config, sync_client, fps: float, ai_ms: float):
        h, w = frame.shape[:2]

        # Barra superior translúcida
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 46), (16, 20, 28), -1)
        cv2.rectangle(overlay, (0, h - 28), (w, h), (16, 20, 28), -1)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

        modo_lbl = "AUTO (ENT/SAI)" if config.modo == "auto" else config.modo.upper()
        cv2.putText(frame, _ascii(f"{config.portal}  |  PASSIVO: {modo_lbl}"), (14, 29),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.54, (240, 245, 255), 1, cv2.LINE_AA)

        status_txt = "API ONLINE" if sync_client.api_online else f"OFFLINE (FILA: {sync_client.pending_count})"
        status_clr = (80, 220, 120) if sync_client.api_online else (60, 175, 255)
        metrics = f"FPS:{fps:4.1f}  IA:{ai_ms:4.0f}ms  CAD:{sync_client.enrolled_count}  {status_txt}"
        text_size = cv2.getTextSize(metrics, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1)[0][0]
        cv2.putText(frame, metrics, (max(10, w - text_size - 14), 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, status_clr, 1, cv2.LINE_AA)

        # Caixas nos rostos rastreados
        for tr in tracks:
            x, y, bw, bh = tr["bbox"]
            person = tr["matched_person"]
            conf = tr["confidence"]

            if person is not None:
                color = (70, 215, 110)
                conf_pct = min(99, max(50, int((conf / 0.75) * 100)))
                title = _ascii(f"{person['nome']} ({conf_pct}%)")
                subtitle = _ascii(f"{person['grupo']} - {person['turno']}")
            else:
                color = (75, 115, 240)
                title = "Identificando..." if not tr["event_sent"] else "Nao cadastrado"
                subtitle = "Fluxo passivo"

            _draw_corner_box(frame, x, y, bw, bh, color, 2)
            pill_y1 = max(48, y - 42)
            pill_y2 = max(48 + 38, y)
            cv2.rectangle(frame, (x, pill_y1), (min(w - 4, max(x + bw, x + 210)), pill_y2), color, -1)
            cv2.putText(frame, title, (x + 6, pill_y1 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (15, 18, 22), 1, cv2.LINE_AA)
            cv2.putText(frame, subtitle, (x + 6, pill_y1 + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.39, (25, 30, 36), 1, cv2.LINE_AA)

        # Pilha discreta de avisos passivos no canto inferior esquerdo
        notices = sync_client.get_recent_notices()
        base_y = h - 40
        for idx, notice in enumerate(reversed(notices)):
            ny = base_y - idx * 30
            if ny < 60:
                break
            clr = (40, 175, 95) if notice["level"] == "ok" else (35, 150, 235)
            txt = _ascii(notice["text"])
            tw = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)[0][0]
            cv2.rectangle(frame, (12, ny - 20), (26 + tw, ny + 6), clr, -1)
            cv2.putText(frame, txt, (19, ny - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.putText(
            frame,
            "[M] Modo (Auto/Entrada/Saida)   [R] Sincronizar Galeria   [T] Testar Passagem   [Q] Sair",
            (14, h - 9),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (185, 195, 210),
            1,
            cv2.LINE_AA,
        )
        return frame
