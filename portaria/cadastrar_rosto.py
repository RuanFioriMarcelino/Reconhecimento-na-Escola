import os
import sys
import argparse
import re
import cv2
import numpy as np
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/api")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTOS_DIR = os.path.join(BASE_DIR, "rostos")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(ROSTOS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

def baixar_modelos():
    urls = {
        YUNET_PATH: "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        SFACE_PATH: "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
    }
    for path, url in urls.items():
        if not os.path.exists(path) or os.path.getsize(path) < 10000:
            print(f"[*] Baixando modelo: {os.path.basename(path)}...")
            r = requests.get(url, allow_redirects=True, timeout=60)
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"[OK] Modelo salvo ({len(r.content)} bytes).")

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip().lower())

def buscar_pessoas():
    try:
        resp = requests.get(f"{API_URL}/bootstrap/", timeout=5)
        if resp.ok:
            data = resp.json()
            return data.get("people", [])
    except Exception as e:
        print(f"[!] Erro ao conectar na API ({API_URL}): {e}")
    return []

def inicializar_modelos():
    baixar_modelos()
    detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), score_threshold=0.8, nms_threshold=0.3)
    recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
    return detector, recognizer

def cadastrar_da_camera(person_id, person_nome, cam_index=0):
    detector, recognizer = inicializar_modelos()
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"[!] Não foi possível acessar a câmera {cam_index}.")
        return False

    print("\n--- CADASTRO FACIAL POR CÂMERA (YuNet + SFace) ---")
    print(f"Pessoa: {person_nome} (ID {person_id})")
    print("Controles:")
    print("  [ESPAÇO] Capturar e salvar biometria facial")
    print("  [ESC/Q]  Cancelar\n")

    window_name = f"Cadastro Facial - {person_nome}"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    saved = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Falha ao ler frame da câmera.")
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(frame)

        display = frame.copy()
        best_face = None

        if faces is not None and len(faces) > 0:
            best_face = faces[0]
            x, y, fw, fh = map(int, best_face[:4])
            score = float(best_face[-1])

            cv2.rectangle(display, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
            cv2.putText(display, f"{person_nome} ({score*100:.0f}%)", (x, max(20, y - 10)),
                        cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 0), 2)

        status_text = "Rosto detectado! Pressione ESPACO para salvar." if best_face is not None else "Posicione o rosto no centro da camera..."
        status_color = (0, 255, 0) if best_face is not None else (0, 165, 255)
        cv2.putText(display, status_text, (20, 35), cv2.FONT_HERSHEY_DUPLEX, 0.65, status_color, 2)
        cv2.putText(display, "[ESPACO] Salvar Biometria   [ESC] Sair", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

        cv2.imshow(window_name, display)
        key = cv2.waitKey(20) & 0xFF
        if key in (27, ord('q')):
            print("Cadastro cancelado.")
            break
        elif key == 32:  # Barra de espaço
            if best_face is not None:
                aligned = recognizer.alignCrop(frame, best_face)
                feature = recognizer.feature(aligned)

                base_name = f"{person_id}_{sanitize_filename(person_nome)}"
                img_path = os.path.join(ROSTOS_DIR, f"{base_name}.jpg")
                feat_path = os.path.join(ROSTOS_DIR, f"{base_name}.npy")

                cv2.imwrite(img_path, aligned)
                np.save(feat_path, feature)
                print(f"\n[SUCESSO] Rosto de '{person_nome}' cadastrado com sucesso!")
                print(f"  Imagem alinhada: {img_path}")
                print(f"  Vetor SFace (128d): {feat_path}")
                saved = True
                break
            else:
                print("[!] Aguarde a detecção do rosto antes de pressionar ESPAÇO.")

    cap.release()
    cv2.destroyAllWindows()
    return saved

def cadastrar_via_imagem(person_id, person_nome, imagem_path):
    if not os.path.exists(imagem_path):
        print(f"[!] Arquivo não encontrado: {imagem_path}")
        return False
    img = cv2.imread(imagem_path)
    if img is None:
        print("[!] Arquivo de imagem inválido.")
        return False

    detector, recognizer = inicializar_modelos()
    h, w = img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img)

    if faces is None or len(faces) == 0:
        print("[!] Nenhum rosto detectado na imagem fornecida.")
        return False

    aligned = recognizer.alignCrop(img, faces[0])
    feature = recognizer.feature(aligned)

    base_name = f"{person_id}_{sanitize_filename(person_nome)}"
    img_path = os.path.join(ROSTOS_DIR, f"{base_name}.jpg")
    feat_path = os.path.join(ROSTOS_DIR, f"{base_name}.npy")

    cv2.imwrite(img_path, aligned)
    np.save(feat_path, feature)
    print(f"\n[SUCESSO] Imagem processada e cadastrada para '{person_nome}'!")
    print(f"  Vetor biométrico gerado: {feat_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Cadastro facial da portaria (YuNet + SFace)")
    parser.add_argument("--id", type=int, help="ID da pessoa no sistema")
    parser.add_argument("--imagem", type=str, help="Caminho de imagem para cadastro")
    parser.add_argument("--cam", type=int, default=0, help="Índice da câmera (padrão: 0)")
    args = parser.parse_args()

    pessoas = buscar_pessoas()
    if not pessoas:
        print("[!] Nenhuma pessoa encontrada. O backend Django está rodando com python manage.py runserver?")
        sys.exit(1)

    pessoa_selecionada = None
    if args.id:
        for p in pessoas:
            if p["id"] == args.id:
                pessoa_selecionada = p
                break
        if not pessoa_selecionada:
            print(f"[!] Pessoa com ID {args.id} não encontrada.")
            sys.exit(1)
    else:
        print("\n=== PESSOAS CADASTRADAS NO BANCO DE DADOS ===")
        for p in pessoas[:15]:
            print(f"[{p['id']}] {p['nome']} ({p['tipo']} - {p['grupo']}) - Turno: {p['turno']}")
        if len(pessoas) > 15:
            print(f"... e mais {len(pessoas) - 15} pessoas.")
        print("=============================================")
        try:
            escolha = int(input("\nDigite o ID da pessoa para capturar o rosto: "))
            for p in pessoas:
                if p["id"] == escolha:
                    pessoa_selecionada = p
                    break
        except (ValueError, KeyboardInterrupt):
            print("\nOperação cancelada.")
            sys.exit(0)

    if not pessoa_selecionada:
        print("[!] ID inválido.")
        sys.exit(1)

    print(f"\nSelecionado: {pessoa_selecionada['nome']} (ID: {pessoa_selecionada['id']})")
    if args.imagem:
        cadastrar_via_imagem(pessoa_selecionada["id"], pessoa_selecionada["nome"], args.imagem)
    else:
        cadastrar_da_camera(pessoa_selecionada["id"], pessoa_selecionada["nome"], cam_index=args.cam)

if __name__ == "__main__":
    main()
