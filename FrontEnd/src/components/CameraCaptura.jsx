import { useEffect, useRef, useState } from 'react';
import Icon from '../icons/Icon.jsx';

export default function CameraCaptura({ onCaptured, errorText = '' }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [previewUrl, setPreviewUrl] = useState('');
  const [localError, setLocalError] = useState('');

  function updatePreview(nextUrl) {
    setPreviewUrl(prev => {
      if (prev && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(prev);
      }
      return nextUrl;
    });
  }

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraOn(false);
  }

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    if (cameraOn && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      const playPromise = videoRef.current.play?.();
      if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(() => {});
      }
    }
  }, [cameraOn]);

  async function startCamera() {
    setLocalError('');
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setLocalError('Navegador sem suporte à webcam ou contexto não seguro (use localhost/HTTPS).');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      setCameraOn(true);
    } catch {
      setLocalError('Permissão da câmera negada ou nenhuma webcam conectada. Você pode enviar uma foto.');
    }
  }

  async function captureThreeFrames() {
    if (!videoRef.current || !cameraOn) return;
    setCapturing(true);
    setLocalError('');
    setProgress(0);

    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    const files = [];

    try {
      for (let i = 0; i < 3; i++) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
        if (blob) {
          files.push(new File([blob], `captura_${i + 1}.jpg`, { type: 'image/jpeg' }));
          if (i === 0) {
            updatePreview(URL.createObjectURL(blob));
          }
        }
        setProgress(i + 1);
        if (i < 2) await new Promise(r => setTimeout(r, 180));
      }
      stopCamera();
      onCaptured(files);
    } catch {
      setLocalError('Erro ao capturar quadros da câmera.');
    } finally {
      setCapturing(false);
    }
  }

  function handleUpload(file) {
    if (!file) return;
    setLocalError('');
    stopCamera();
    updatePreview(URL.createObjectURL(file));
    onCaptured([file]);
  }

  const displayError = errorText || localError;

  return (
    <div className="capture-box">
      {cameraOn ? (
        <div style={{ position: 'relative', maxWidth: 320, margin: '0 auto 14px', borderRadius: 10, overflow: 'hidden', background: '#111827' }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', display: 'block', transform: 'scaleX(-1)' }}
          />
          <div
            style={{
              position: 'absolute',
              inset: '14% 24%',
              border: '2px dashed rgba(255,255,255,0.75)',
              borderRadius: '50%',
              pointerEvents: 'none',
            }}
          />
        </div>
      ) : previewUrl ? (
        <div style={{ margin: '0 auto 14px', width: 112, height: 112, borderRadius: '50%', overflow: 'hidden', border: '2px solid var(--good)' }}>
          <img src={previewUrl} alt="Prévia facial" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      ) : (
        <div className="capture-preview">
          <Icon name="camera" size={30} />
        </div>
      )}

      <div className="capture-status">
        {capturing
          ? `Capturando quadro ${progress}/3... mantenha o rosto parado.`
          : cameraOn
          ? 'Centralize apenas 1 rosto dentro do guia oval e clique em Capturar.'
          : previewUrl
          ? <span style={{ color: 'var(--good)', fontWeight: 600 }}><Icon name="check" size={13} /> Captura pronta para validação biométrica (3 quadros / foto).</span>
          : 'Estação de registro dedicada: abra a webcam local ou envie uma foto nítida.'}
      </div>

      {displayError && (
        <div style={{ fontSize: 12.5, color: 'var(--danger)', marginBottom: 12, fontWeight: 500 }}>
          {displayError}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
        {!cameraOn ? (
          <button type="button" className="btn btn-primary" onClick={startCamera}>
            <Icon name="camera" size={16} /> {previewUrl ? 'Reabrir câmera' : 'Abrir câmera de registro'}
          </button>
        ) : (
          <>
            <button type="button" className="btn btn-primary" disabled={capturing} onClick={captureThreeFrames}>
              <Icon name="scan" size={16} /> {capturing ? `Capturando (${progress}/3)` : 'Capturar biometria (3 quadros)'}
            </button>
            <button type="button" className="btn btn-ghost" disabled={capturing} onClick={stopCamera}>
              Fechar câmera
            </button>
          </>
        )}

        <label className="btn btn-ghost" style={{ cursor: 'pointer' }}>
          <Icon name="edit" size={15} /> Enviar foto
          <input type="file" accept="image/*" hidden onChange={e => handleUpload(e.target.files?.[0])} />
        </label>
      </div>
    </div>
  );
}
