import argparse
import getpass
import sys
import time
from pathlib import Path

import cv2
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from portaria.camera import CameraStream
from portaria.config import load_config
from portaria.models_loader import create_face_models


def autenticar(api_url: str, email: str | None, senha: str | None) -> str:
    email = email or input("E-mail institucional (coordenação/secretaria/admin): ").strip()
    senha = senha or getpass.getpass("Senha: ")
    resp = requests.post(f"{api_url}/login/", json={"email": email, "senha": senha}, timeout=6)
    if not resp.ok:
        detail = resp.json().get("detail", "Falha na autenticação.") if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise RuntimeError(f"Erro no login ({resp.status_code}): {detail}")
    return resp.json()["token"]


def listar_pessoas(api_url: str, token: str) -> list[dict]:
    resp = requests.get(
        f"{api_url}/people/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=6,
    )
    resp.raise_for_status()
    return resp.json().get("people", [])


def enviar_biometria(api_url: str, token: str, person_uid: str, frames_jpeg: list[bytes]):
    files = [("imagens", (f"quadro_{idx + 1}.jpg", data, "image/jpeg")) for idx, data in enumerate(frames_jpeg)]
    resp = requests.post(
        f"{api_url}/people/{person_uid}/biometrics/",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        timeout=15,
    )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"detail": resp.text}
    if not resp.ok:
        raise RuntimeError(data.get("detail", f"Falha HTTP {resp.status_code}"))
    return data


def capturar_da_camera(api_url: str, token: str, pessoa: dict, config):
    detector, _ = create_face_models(config.models_dir, score_threshold=0.80)
    cam = CameraStream(source=config.source, width=config.width, height=config.height)
    if not cam.start():
        raise RuntimeError(f"Não foi possível abrir a câmera ({config.source}).")

    print("\n--- ESTAÇÃO DE CADASTRO BIOMÉTRICO (3 QUADROS EM MEMÓRIA) ---")
    print(f"Pessoa: {pessoa['nome']} ({pessoa['id']})")
    print("Controles: [ESPAÇO] Capturar 3 quadros e enviar ao PostgreSQL  |  [ESC/Q] Cancelar\n")

    window_name = f"Cadastro Biometrico - {pessoa['nome']}"
    try:
        while True:
            frame, _ = cam.read()
            if frame is None:
                time.sleep(0.01)
                continue

            h, w = frame.shape[:2]
            det_w = min(w, config.detect_width)
            scale = det_w / float(w)
            small = cv2.resize(frame, (det_w, int(h * scale))) if scale < 0.99 else frame
            detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = detector.detect(small)

            display = frame.copy()
            face_count = len(faces) if faces is not None else 0
            if face_count == 1:
                inv = 1.0 / scale if scale < 0.99 else 1.0
                fx, fy, fw, fh = [int(v * inv) for v in faces[0][:4]]
                cv2.rectangle(display, (fx, fy), (fx + fw, fy + fh), (70, 215, 110), 2)
                msg = "Enquadramento OK! Pressione ESPACO para capturar 3 quadros."
                clr = (70, 215, 110)
            elif face_count > 1:
                msg = "Mais de um rosto detectado! Deixe apenas 1 pessoa."
                clr = (40, 140, 255)
            else:
                msg = "Posicione o rosto no centro da camera..."
                clr = (40, 180, 255)

            cv2.rectangle(display, (0, 0), (w, 48), (18, 22, 30), -1)
            cv2.putText(display, msg, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.56, clr, 1, cv2.LINE_AA)
            cv2.imshow(window_name, display)

            key = cv2.waitKey(15) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                print("Cadastro cancelado.")
                return
            if key == 32:  # ESPAÇO
                if face_count != 1:
                    print("[!] Aguarde exatamente 1 rosto visível antes de capturar.")
                    continue
                frames_jpeg = []
                for idx in range(3):
                    snap, _ = cam.read()
                    if snap is not None:
                        ok, encoded = cv2.imencode(".jpg", snap, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        if ok:
                            frames_jpeg.append(encoded.tobytes())
                    time.sleep(0.15)

                print("[*] Validando qualidade e criptografando biometria no servidor...")
                try:
                    res = enviar_biometria(api_url, token, pessoa["id"], frames_jpeg)
                    print(f"[SUCESSO] Biometria criptografada salva no PostgreSQL! Qualidade: {res['qualidade']:.2f} (chave {res['keyId']})")
                    return
                except Exception as error:
                    print(f"[!] Servidor rejeitou a captura: {error}")
                    print("    Ajuste posição/iluminação e tente pressionar ESPAÇO novamente.")
    finally:
        cam.stop()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Estação CLI de Cadastro Biométrico (criptografado no PostgreSQL)")
    parser.add_argument("--id", type=str, help="ID da pessoa (ex: aluno-1 ou funcionario-2)")
    parser.add_argument("--imagem", type=str, help="Caminho de imagem existente para enviar")
    parser.add_argument("--cam", type=str, help="Índice da câmera (padrão do .env)")
    parser.add_argument("--email", type=str, help="E-mail institucional para autenticação")
    parser.add_argument("--senha", type=str, help="Senha institucional")
    args = parser.parse_args()

    config = load_config(source_override=args.cam)
    try:
        token = autenticar(config.api_url, args.email, args.senha)
        pessoas = listar_pessoas(config.api_url, token)
    except Exception as error:
        print(f"[!] {error}")
        sys.exit(1)

    selecionada = None
    if args.id:
        selecionada = next((p for p in pessoas if str(p["id"]) == args.id or str(p["realId"]) == args.id), None)
        if selecionada is None:
            print(f"[!] Pessoa '{args.id}' não encontrada.")
            sys.exit(1)
    else:
        print("\n=== PESSOAS CADASTRADAS ===")
        for p in pessoas[:25]:
            bio_tag = "BIOMETRIA OK" if p.get("biometriaCadastrada") else "SEM BIOMETRIA"
            print(f"  [{p['id']}] {p['nome']} ({p['grupo']}) -> {bio_tag}")
        if len(pessoas) > 25:
            print(f"  ... e mais {len(pessoas) - 25} pessoas.")
        escolha = input("\nDigite o ID (ex: aluno-1): ").strip()
        selecionada = next((p for p in pessoas if str(p["id"]) == escolha), None)
        if selecionada is None:
            print("[!] ID inválido.")
            sys.exit(1)

    if args.imagem:
        path = Path(args.imagem)
        if not path.exists():
            print(f"[!] Arquivo não encontrado: {path}")
            sys.exit(1)
        res = enviar_biometria(config.api_url, token, selecionada["id"], [path.read_bytes()])
        print(f"[SUCESSO] Biometria salva para {selecionada['nome']} (qualidade={res['qualidade']:.2f}).")
    else:
        capturar_da_camera(config.api_url, token, selecionada, config)


if __name__ == "__main__":
    main()
