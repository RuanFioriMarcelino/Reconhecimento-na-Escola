import os
import sys
import time
import argparse
import random
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

COSINE_THRESHOLD = 0.363  # Limiar padrão oficial do OpenCV SFace

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

class PortariaReconhecimento:
    def __init__(self, api_url=API_URL, portal="Portaria principal"):
        self.api_url = api_url.rstrip("/")
        self.portal = portal
        self.tipo_movimento = "entrada"
        self.cooldown_seconds = 15
        self.last_registered = {}
        self.enrolled_faces = []  # list of {'id', 'nome', 'tipo', 'grupo', 'feature'}
        self.people_dict = {}
        self.last_event_msg = ""
        self.last_event_time = 0
        self.unknown_detected_start = None

        baixar_modelos()
        self.detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), score_threshold=0.8, nms_threshold=0.3)
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")

    def carregar_dados_api(self):
        try:
            resp = requests.get(f"{self.api_url}/bootstrap/", timeout=4)
            if resp.ok:
                data = resp.json()
                for p in data.get("people", []):
                    self.people_dict[p["id"]] = p
                print(f"[OK] Conectado ao Django! {len(self.people_dict)} pessoas no cadastro escolar.")
                return True
        except Exception as e:
            print(f"[!] Não foi possível conectar ao backend ({self.api_url}): {e}")
        return False

    def carregar_rostos_cadastrados(self):
        self.enrolled_faces = []
        if not os.path.exists(ROSTOS_DIR):
            return

        for fname in os.listdir(ROSTOS_DIR):
            if fname.lower().endswith(".npy"):
                try:
                    parts = fname.split("_", 1)
                    person_id = int(parts[0])
                    feat_path = os.path.join(ROSTOS_DIR, fname)
                    feature = np.load(feat_path)

                    person_info = self.people_dict.get(person_id, {
                        "id": person_id,
                        "nome": parts[1].rsplit(".", 1)[0].replace("_", " ").title(),
                        "tipo": "aluno" if person_id < 10000 else "funcionario",
                        "grupo": "Escola",
                    })

                    self.enrolled_faces.append({
                        "id": person_id,
                        "nome": person_info["nome"],
                        "tipo": person_info.get("tipo", "aluno"),
                        "grupo": person_info.get("grupo", ""),
                        "feature": feature,
                    })
                except Exception as e:
                    print(f"[!] Erro ao carregar biometria {fname}: {e}")

        print(f"[OK] {len(self.enrolled_faces)} biometria(s) facial(is) carregada(s).")

    def registrar_acesso(self, person_id=None, person_nome="Desconhecido", status_force=None):
        now = time.time()
        key = person_id if person_id is not None else "unknown"
        if key in self.last_registered and (now - self.last_registered[key] < self.cooldown_seconds):
            return

        payload = {
            "personId": person_id,
            "tipo": self.tipo_movimento,
            "portal": self.portal,
        }
        if status_force:
            payload["status"] = status_force

        try:
            resp = requests.post(f"{self.api_url}/access/", json=payload, timeout=3)
            if resp.ok:
                result = resp.json()
                self.last_registered[key] = now
                status_txt = result.get("status", "registrado").upper()
                name_txt = result.get("personName") or "Não Reconhecido"
                self.last_event_msg = f"{status_txt}: {name_txt} ({self.tipo_movimento.upper()})"
                self.last_event_time = now
                print(f"[ACESSO REGISTRADO] {self.last_event_msg} - ID {result.get('id')}")
            else:
                print(f"[!] Erro no registro: HTTP {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[!] Erro de conexão ao enviar acesso: {e}")

    def comparar_rosto(self, face_feature):
        if not self.enrolled_faces:
            return None, 0.0

        best_match = None
        best_score = -1.0

        for candidate in self.enrolled_faces:
            score = self.recognizer.match(face_feature, candidate["feature"], cv2.FaceRecognizerSF_FR_COSINE)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_score >= COSINE_THRESHOLD:
            conf_perc = min(99.0, max(50.0, ((best_score - 0.3) / 0.5) * 100))
            return best_match, conf_perc
        return None, max(0.0, best_score * 100)

    def simular_acesso_teste(self):
        if self.people_dict:
            p = random.choice(list(self.people_dict.values()))
            print(f"\n[TESTE] Simulando reconhecimento de: {p['nome']} (ID {p['id']})")
            self.registrar_acesso(p['id'], p['nome'])
        else:
            print("[TESTE] Simulando tentativa não reconhecida.")
            self.registrar_acesso(None, "Desconhecido")

    def executar(self, cam_index=0, video_path=None):
        self.carregar_dados_api()
        self.carregar_rostos_cadastrados()

        source = video_path if video_path else cam_index
        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"\n[AVISO] Nenhuma câmera física acessível no índice {source}.")
            print("Iniciando Modo Interativo de Demonstração...\n")
            self.executar_modo_demo()
            return

        window_name = "Portaria Escolar - Reconhecimento Facial (YuNet + SFace)"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

        print("\n=== MONITORAMENTO FACIAL DA PORTARIA INICIADO ===")
        print("Atalhos do teclado:")
        print("  [S] Alternar entre ENTRADA e SAÍDA")
        print("  [T] Simular acesso teste (envia para o painel)")
        print("  [C] Cadastrar novo rosto na câmera")
        print("  [Q/ESC] Encerrar\n")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[!] Fim do fluxo de vídeo.")
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(frame)

            current_time = time.time()
            face_detected = faces is not None and len(faces) > 0
            matched_any = False

            # Header HUD
            cv2.rectangle(frame, (0, 0), (w, 50), (24, 24, 24), -1)
            mode_color = (40, 200, 40) if self.tipo_movimento == "entrada" else (220, 150, 40)
            cv2.putText(frame, f"MODO: {self.tipo_movimento.upper()}", (15, 33),
                        cv2.FONT_HERSHEY_DUPLEX, 0.7, mode_color, 2)
            cv2.putText(frame, f"PORTAL: {self.portal}", (210, 33),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (220, 220, 220), 1)

            api_status_txt = "API: ONLINE" if self.people_dict else "API: OFFLINE"
            api_color = (50, 220, 50) if self.people_dict else (50, 50, 220)
            cv2.putText(frame, api_status_txt, (w - 170, 33), cv2.FONT_HERSHEY_DUPLEX, 0.55, api_color, 2)

            if face_detected:
                for face in faces:
                    x, y, fw, fh = map(int, face[:4])
                    aligned = self.recognizer.alignCrop(frame, face)
                    feat = self.recognizer.feature(aligned)
                    person, conf = self.comparar_rosto(feat)

                    if person:
                        matched_any = True
                        self.unknown_detected_start = None
                        color = (0, 220, 0)
                        label = f"{person['nome']} ({conf:.0f}%)"
                        sublabel = f"{person['tipo'].title()} - {person.get('grupo', '')}"
                        self.registrar_acesso(person['id'], person['nome'])
                    else:
                        color = (0, 60, 230)
                        label = "Nao Reconhecido"
                        sublabel = "Sem cadastro facial"

                    # Bounding Box e Tags
                    cv2.rectangle(frame, (x, y), (x + fw, y + fh), color, 2)
                    cv2.rectangle(frame, (x, max(0, y - 42)), (x + fw, y), color, -1)
                    cv2.putText(frame, label, (x + 6, max(18, y - 24)),
                                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(frame, sublabel, (x + 6, max(32, y - 8)),
                                cv2.FONT_HERSHEY_DUPLEX, 0.42, (240, 240, 240), 1)

            # Lógica para presença desconhecida contínua
            if face_detected and not matched_any:
                if self.unknown_detected_start is None:
                    self.unknown_detected_start = current_time
                elif current_time - self.unknown_detected_start > 3.0:
                    self.registrar_acesso(None, "Desconhecido")
                    self.unknown_detected_start = current_time
            else:
                self.unknown_detected_start = None

            # Feedback visual de evento registrado
            if self.last_event_msg and (current_time - self.last_event_time < 4.0):
                banner_color = (0, 180, 0) if "RECONHECIDO" in self.last_event_msg else (0, 100, 220)
                cv2.rectangle(frame, (0, h - 45), (w, h), banner_color, -1)
                cv2.putText(frame, self.last_event_msg, (20, h - 16),
                            cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 2)
            else:
                cv2.rectangle(frame, (0, h - 28), (w, h), (15, 15, 15), -1)
                cv2.putText(frame, "[S] Modo  [T] Simular Teste  [C] Cadastrar  [Q] Sair",
                            (15, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord('q')):
                break
            elif key == ord('s'):
                self.tipo_movimento = "saida" if self.tipo_movimento == "entrada" else "entrada"
                print(f"[*] Modo alterado para: {self.tipo_movimento.upper()}")
            elif key == ord('t'):
                self.simular_acesso_teste()
            elif key == ord('c'):
                cap.release()
                cv2.destroyAllWindows()
                os.system(f'"{sys.executable}" "{os.path.join(BASE_DIR, "cadastrar_rosto.py")}"')
                return self.executar(cam_index, video_path)

        cap.release()
        cv2.destroyAllWindows()

    def executar_modo_demo(self):
        print("=== MODO SIMULAÇÃO DA PORTARIA ===")
        print("Opções disponíveis:")
        print("  [1] Simular acesso de aluno/funcionário cadastrado")
        print("  [2] Simular tentativa não reconhecida (gera alerta)")
        print("  [3] Alternar sentido (Entrada / Saída)")
        print("  [4] Recarregar cadastros da API")
        print("  [0] Sair\n")

        while True:
            try:
                cmd = input(f"[{self.tipo_movimento.upper()} @ {self.portal}] Escolha: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if cmd == "1":
                self.simular_acesso_teste()
            elif cmd == "2":
                self.registrar_acesso(None, "Desconhecido")
            elif cmd == "3":
                self.tipo_movimento = "saida" if self.tipo_movimento == "entrada" else "entrada"
                print(f"[*] Sentido alterado para: {self.tipo_movimento.upper()}")
            elif cmd == "4":
                self.carregar_dados_api()
                self.carregar_rostos_cadastrados()
            elif cmd in ("0", "q", "exit"):
                print("Encerrando portaria.")
                break

def main():
    parser = argparse.ArgumentParser(description="Módulo de Reconhecimento Facial da Portaria (YuNet + SFace)")
    parser.add_argument("--cam", type=int, default=0, help="Índice da câmera (padrão: 0)")
    parser.add_argument("--video", type=str, help="Caminho para arquivo de vídeo")
    parser.add_argument("--portal", type=str, default="Portaria principal", help="Nome do portal")
    parser.add_argument("--demo", action="store_true", help="Iniciar diretamente no modo interativo")
    args = parser.parse_args()

    portaria = PortariaReconhecimento(portal=args.portal)
    if args.demo:
        portaria.carregar_dados_api()
        portaria.executar_modo_demo()
    else:
        portaria.executar(cam_index=args.cam, video_path=args.video)

if __name__ == "__main__":
    main()
