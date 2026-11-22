import React from "react";

interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "warning" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  title,
  description,
  confirmText = "Confirm Action",
  cancelText = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-md bg-surface border border-surface-border rounded-xl shadow-2xl overflow-hidden p-6">
        <div className="flex items-center space-x-3 mb-4">
          <div className={
            variant === "danger"
              ? "w-10 h-10 rounded-full bg-danger/10 border border-danger/30 flex items-center justify-center text-danger"
              : variant === "warning"
              ? "w-10 h-10 rounded-full bg-warning/10 border border-warning/30 flex items-center justify-center text-warning"
              : "w-10 h-10 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary"
          }>
            <span className="material-symbols-rounded text-2xl">
              {variant === "danger" ? "warning" : "info"}
            </span>
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100">{title}</h3>
            <p className="text-xs text-muted">Operator confirmation required</p>
          </div>
        </div>

        <p className="text-sm text-slate-300 mb-6 leading-relaxed bg-surface-card p-3 rounded-lg border border-surface-border font-mono text-xs">
          {description}
        </p>

        <div className="flex items-center justify-end space-x-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg bg-surface-card hover:bg-surface-border text-xs font-medium text-slate-300 border border-surface-border transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={
              variant === "danger"
                ? "px-4 py-2 rounded-lg bg-danger hover:bg-danger/90 text-xs font-semibold text-white shadow-[0_0_15px_rgba(239,68,68,0.3)] transition-all"
                : "px-4 py-2 rounded-lg bg-primary hover:bg-primary-hover text-xs font-semibold text-background transition-all"
            }
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
