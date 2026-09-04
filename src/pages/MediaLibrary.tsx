import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useNavigate } from "react-router-dom";
import { useActiveCase } from "../hooks/useActiveCase";

export default function MediaLibraryPage() {
  const { active } = useActiveCase();
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const browseMedia = async () => {
    const sel = await open({
      multiple: false,
      title: "Open extracted video for forensic preview",
      filters: [{ name: "Video Files", extensions: ["mp4", "mkv", "avi", "mov", "dav", "hik"] }],
    });
    if (typeof sel === "string") {
      setSelectedFile(sel);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-100">Forensic Media Library</h1>
          <p className="text-sm text-ink-400 mt-1">
            Browse, inspect, and preview extracted DVR recordings and carved candidate streams.
          </p>
        </div>
        <button className="btn btn-primary" onClick={browseMedia}>
          Open Video Clip
        </button>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Open a case to review its media evidence catalog.
        </div>
      ) : (
        <div className="space-y-6">
          {selectedFile ? (
            <div className="card space-y-4">
              <div className="flex items-center justify-between border-b border-ink-700 pb-3">
                <div>
                  <h2 className="text-lg font-semibold text-ink-100">
                    {selectedFile.split(/[\\/]/).pop()}
                  </h2>
                  <div className="text-xs text-ink-400 font-mono mt-1">{selectedFile}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn"
                    onClick={() => navigate("/analytics")}
                  >
                    Send to AI Analytics
                  </button>
                </div>
              </div>

              <div className="bg-black rounded-lg aspect-video flex items-center justify-center border border-ink-800">
                <div className="text-center p-6 space-y-2">
                  <div className="text-3xl">🎥</div>
                  <div className="text-sm text-ink-300">
                    Video Stream Loaded: <span className="font-mono text-blue-300">{selectedFile.split(/[\\/]/).pop()}</span>
                  </div>
                  <div className="text-xs text-ink-400">
                    Read-only forensic sandbox. Codec: H.264/H.265 remux.
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card text-center p-12 space-y-3">
              <div className="text-4xl text-ink-400">📁</div>
              <h3 className="text-lg font-semibold text-ink-200">No Video Clip Selected</h3>
              <p className="text-sm text-ink-400 max-w-md mx-auto">
                Videos extracted from DVR disk images or recovered via GOP carving will be available here for inspection.
              </p>
              <div className="pt-2">
                <button className="btn btn-primary" onClick={browseMedia}>
                  Browse &amp; Select Video
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}