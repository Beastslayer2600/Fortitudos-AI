import * as React from "react";
import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex min-h-[88px] w-full rounded-md bg-elevated px-3 py-2.5 text-sm text-fg shadow-[var(--shadow-border)]",
      "placeholder:text-subtle",
      "transition-[box-shadow] duration-150",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
      "disabled:cursor-not-allowed disabled:opacity-40",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
