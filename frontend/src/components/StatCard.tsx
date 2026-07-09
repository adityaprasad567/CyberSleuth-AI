import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useEffect } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => `${Math.round(v).toLocaleString()}${suffix}`);
  useEffect(() => {
    const controls = animate(count, value, { duration: 1.2, ease: "easeOut" });
    return () => controls.stop();
  }, [value]);
  return <motion.span>{rounded}</motion.span>;
}

export function StatCard({
  icon: Icon,
  label,
  value,
  suffix,
  accent = "primary",
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  suffix?: string;
  accent?: "primary" | "cyan" | "success" | "warning";
}) {
  const accentMap = {
    primary: "bg-primary/10 text-primary",
    cyan: "bg-cyan/15 text-cyan",
    success: "bg-success/15 text-success",
    warning: "bg-warning/20 text-warning",
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-card rounded-xl p-5 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</div>
          <div className="mt-2 text-3xl font-bold tracking-tight">
            <AnimatedNumber value={value} suffix={suffix} />
          </div>
        </div>
        <div className={cn("grid h-10 w-10 place-items-center rounded-lg shrink-0", accentMap[accent])}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </motion.div>
  );
}
