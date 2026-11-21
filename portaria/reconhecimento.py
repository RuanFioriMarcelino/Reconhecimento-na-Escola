import argparse
import os
import random
import sys
import time
from pathlib import Path

import cv2

cv2.setNumThreads(max(1, min(4, os.cpu_count() or 1)))

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from portaria.camera import CameraStream
from portaria.config import load_config
from portaria.engine import RecognitionWorker
from portaria.hud import HudRenderer
from portaria.sync_client import SyncClient

MODOS = ["auto", "entrada", "saida"]


def _pick_test_uid(sync_client: SyncClient, gallery_meta: list[dict] | None = None) -> tuple[str | None, str]:
    if gallery_meta:
        chosen = random.choice(gallery_meta)
        return chosen["uid"], chosen["nome"]
    if sync_client.sample_people:
        chosen = random.choice(sync_client.sample_people)
        return chosen["uid"], chosen["nome"]
    return None, "Rosto não cadastrado"


def executar_modo_demo(config, sync_client: SyncClient):
    print("\n=== PORTARIA PASSIVA — MODO DEMONSTRAÇÃO (SEM CÂMERA) ===")
    print("Atalhos:")
    print("  [1] Simular passagem de pessoa cadastrada")
    print("  [2] Simular rosto não cadastrado (gera aviso/alerta)")
    print("  [3] Alternar sentido (AUTO / ENTRADA / SAIDA)")
    print("  [4] Sincronizar galeria biométrica agora")
    print("  [0] Sair\n")

    while True:
        try:
            cmd = input(f"[{config.modo.upper()} | {config.portal} | fila={sync_client.pending_count}] Escolha: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if cmd == "1":
            uid, nome = _pick_test_uid(sync_client)
            sync_client.enqueue_event(uid, config.modo, config.portal, 0.72 if uid else None)
            print(f"[ENVIADO] Passagem simulada para {nome} ({uid or 'não cadastrado'}, modo={config.modo}).")
        elif cmd == "2":
            sync_client.enqueue_event(None, config.modo, config.portal, None)
            print("[ENVIADO] Passagem não reconhecida simulada.")
        elif cmd == "3":
            idx = (MODOS.index(config.modo) + 1) % len(MODOS)
            config.modo = MODOS[idx]
            print(f"[*] Modo alterado para: {config.modo.upper()}")
        elif cmd == "4":
            sync_client.force_gallery_sync()
            print("[*] Sincronização da galeria solicitada.")
        elif cmd in ("0", "q", "exit"):
            break


def main():
    parser = argparse.ArgumentParser(description="Portaria Escolar Passiva v2.0 (YuNet + SFace + Spool Offline)")
    parser.add_argument("--source", type=str, help="Índice da câmera (0), URL RTSP ou arquivo de vídeo")
    parser.add_argument("--portal", type=str, help="Nome do portal (ex: Portaria principal)")
    parser.add_argument("--modo", choices=MODOS, help="Sentido padrão: auto, entrada ou saida")
    parser.add_argument("--headless", action="store_true", help="Executa sem abrir janela gráfica")
    parser.add_argument("--demo", action="store_true", help="Executa no modo interativo de terminal")
    args = parser.parse_args()

    config = load_config(
        source_override=args.source,
        portal_override=args.portal,
        modo_override=args.modo,
        headless_override=True if args.headless else None,
    )

    if not config.device_key:
        print("[!] ATENÇÃO: PORTARIA_DEVICE_KEY não configurada em portaria/.env.")
        print("    Gere uma chave no painel Web (Configurações -> Câmeras de Portaria) ou use PORTARIA_DEV_KEY.")

    sync_client = SyncClient(
        api_url=config.api_url,
        device_key=config.device_key,
        spool_db_path=config.spool_db_path,
    )

    if args.demo:
        sync_client.start()
        try:
            executar_modo_demo(config, sync_client)
        finally:
            sync_client.stop()
        return

    camera = CameraStream(source=config.source, width=config.width, height=config.height)
    worker = RecognitionWorker(config=config, camera_stream=camera, sync_client=sync_client)

    sync_client.on_gallery_updated = worker.update_gallery
    sync_client.on_config_updated = worker.update_config
    sync_client.set_telemetry_provider(
        lambda: {
            "fps": round(camera.fps, 1),
            "aiMs": round(worker.last_ai_ms, 1),
            "cameraOk": camera.connected,
        }
    )

    sync_client.start()
    if not camera.start():
        print(f"\n[AVISO] Câmera/fonte '{config.source}' indisponível no momento.")
        executar_modo_demo(config, sync_client)
        sync_client.stop()
        return

    worker.start()
    hud = HudRenderer()
    window_name = f"Reconhece+ Portaria Passiva - {config.portal}"

    print("\n=== PORTARIA PASSIVA v2.0 INICIADA ===")
    print(f"Portal: {config.portal} | Modo: {config.modo.upper()} | Fonte: {config.source}")
    print("Atalhos: [M] Modo (Auto/Entrada/Saída) | [R] Atualizar Galeria | [T] Testar Passagem | [Q] Sair\n")

    try:
        while True:
            if camera.eof:
                print("[*] Fim do arquivo de vídeo.")
                break

            frame, _ = camera.read()
            if frame is None:
                time.sleep(0.015)
                continue

            if not config.headless:
                tracks = worker.get_tracks_snapshot()
                annotated = hud.render(frame, tracks, config, sync_client, camera.fps, worker.last_ai_ms)
                cv2.imshow(window_name, annotated)
                key = cv2.waitKey(15) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
                elif key in (ord("m"), ord("M")):
                    idx = (MODOS.index(config.modo) + 1) % len(MODOS)
                    config.modo = MODOS[idx]
                    sync_client.push_notice(f"Modo alterado para {config.modo.upper()}", "ok")
                elif key in (ord("r"), ord("R")):
                    sync_client.force_gallery_sync()
                    sync_client.push_notice("Sincronizando galeria...", "ok")
                elif key in (ord("t"), ord("T")):
                    uid, nome = _pick_test_uid(sync_client, worker._gallery_meta)
                    sync_client.enqueue_event(uid, config.modo, config.portal, 0.75 if uid else None)
                    sync_client.push_notice(f"Teste enviado: {nome}", "ok")
            else:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[*] Encerrando portaria...")
    finally:
        worker.stop()
        camera.stop()
        sync_client.stop()
        if not config.headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
