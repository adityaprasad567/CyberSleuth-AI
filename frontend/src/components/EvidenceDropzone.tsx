import { useCallback, useRef, useState } from "react";
import { UploadCloud, X, FileText, ImageIcon, FileAudio, FileVideo, File as FileIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

function iconFor(type: string) {
  if (type.startsWith("image/")) return ImageIcon;
  if (type.startsWith("audio/")) return FileAudio;
  if (type.startsWith("video/")) return FileVideo;
  if (type.includes("pdf")) return FileText;
  return FileIcon;
}

export function EvidenceDropzone({
  files,
  onChange,
  progress,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  progress?: number;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const add = useCallback(
    (list: FileList | null) => {
      if (!list) return;
      onChange([...files, ...Array.from(list)]);
    },
    [files, onChange],
  );

  const remove = (idx: number) => onChange(files.filter((_, i) => i !== idx));

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setHover(true); }}
        onDragLeave={() => setHover(false)}
        onDrop={(e) => { e.preventDefault(); setHover(false); add(e.dataTransfer.files); }}
        onClick={() => input.current?.click()}
        className={cn(
          "cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all",
          hover ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30",
          disabled && "opacity-50 pointer-events-none",
        )}
      >
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-primary/10 text-primary mb-3">
          <UploadCloud className="h-6 w-6" />
        </div>
        <div className="text-sm font-medium">Drag & drop evidence files here</div>
        <div className="text-xs text-muted-foreground mt-1">
          Images, PDFs, audio & video — multiple files supported
        </div>
        <input
          ref={input}
          type="file"
          multiple
          accept="image/*,application/pdf,audio/*,video/*"
          className="hidden"
          onChange={(e) => add(e.target.files)}
        />
      </div>

      {typeof progress === "number" && progress > 0 && progress < 100 && (
        <div>
          <Progress value={progress} className="h-1.5" />
          <div className="text-xs text-muted-foreground mt-1">Uploading… {progress}%</div>
        </div>
      )}

      {files.length > 0 && (
        <ul className="space-y-1.5">
          {files.map((f, i) => {
            const Icon = iconFor(f.type);
            return (
              <li key={i} className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2">
                <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{f.name}</div>
                  <div className="text-[11px] text-muted-foreground">{(f.size / 1024).toFixed(1)} KB</div>
                </div>
                <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={(e) => { e.stopPropagation(); remove(i); }}>
                  <X className="h-3.5 w-3.5" />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
