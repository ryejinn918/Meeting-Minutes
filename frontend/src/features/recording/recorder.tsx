import { Mic, Pause, Play, RotateCcw, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearChunks, loadChunks, saveChunk } from "@/features/recording/recording-storage";

const TYPES = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
const DRAFT = "new-meeting";

export function Recorder({ onFile }: { onFile: (file: File | null) => void }) {
  const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null);
  const index = useRef(0); const started = useRef(0);
  const [state, setState] = useState<"idle" | "recording" | "paused" | "ready">("idle");
  const [seconds, setSeconds] = useState(0); const [error, setError] = useState(""); const [url, setUrl] = useState("");
  const buildFile = useCallback(async (mime: string) => {
    const chunks = await loadChunks(DRAFT); if (!chunks.length) return;
    const extension = mime.includes("mp4") ? "m4a" : mime.includes("ogg") ? "ogg" : "webm";
    const file = new File(chunks, `meetflow-${Date.now()}.${extension}`, { type: mime.split(";")[0] });
    onFile(file); setUrl(URL.createObjectURL(file)); setState("ready");
  }, [onFile]);
  useEffect(() => { void loadChunks(DRAFT).then((chunks) => { if (chunks.length) void buildFile(chunks[0].type || "audio/webm"); }); return () => { stream.current?.getTracks().forEach((track) => track.stop()); }; }, [buildFile]);
  useEffect(() => { if (state !== "recording") return; const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started.current) / 1000)), 1000); return () => clearInterval(timer); }, [state]);
  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return setError("이 브라우저에서는 직접 녹음을 지원하지 않아요.");
    try {
      await clearChunks(DRAFT); index.current = 0; onFile(null); setUrl("");
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
      recorder.current = new MediaRecorder(stream.current, mime ? { mimeType: mime } : undefined);
      recorder.current.ondataavailable = (event) => { if (event.data.size) void saveChunk(DRAFT, index.current++, event.data); };
      recorder.current.onstop = () => { stream.current?.getTracks().forEach((track) => track.stop()); void buildFile(recorder.current?.mimeType || "audio/webm"); };
      recorder.current.start(5000); started.current = Date.now(); setSeconds(0); setState("recording"); setError("");
    } catch { setError("마이크 권한을 허용하고 다시 시도해 주세요."); }
  }
  const stop = () => recorder.current?.stop();
  return <div className="space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4"><p className="text-sm font-bold text-slate-800">직접 녹음</p><p className="text-xs text-slate-500">화면 잠금이나 다른 앱 전환 시 녹음이 중단될 수 있어요.</p><p aria-live="polite" className="text-2xl font-bold tabular-nums text-indigo-700">{String(Math.floor(seconds / 60)).padStart(2,"0")}:{String(seconds % 60).padStart(2,"0")}</p><div className="flex flex-wrap gap-2">{state === "idle" && <Button onClick={() => void start()} type="button"><Mic className="h-4 w-4" />녹음 시작</Button>}{state === "recording" && <><Button onClick={() => { recorder.current?.pause(); setState("paused"); }} type="button" variant="outline"><Pause className="h-4 w-4" />일시정지</Button><Button onClick={stop} type="button" variant="danger"><Square className="h-4 w-4" />종료</Button></>}{state === "paused" && <><Button onClick={() => { recorder.current?.resume(); started.current = Date.now() - seconds * 1000; setState("recording"); }} type="button"><Play className="h-4 w-4" />계속</Button><Button onClick={stop} type="button" variant="danger">종료</Button></>}{state === "ready" && <Button onClick={() => void clearChunks(DRAFT).then(() => { onFile(null); setState("idle"); setUrl(""); })} type="button" variant="outline"><RotateCcw className="h-4 w-4" />다시 녹음</Button>}</div>{url && <audio className="w-full" controls src={url} />}{error && <p className="text-sm text-rose-700" role="alert">{error}</p>}</div>;
}
