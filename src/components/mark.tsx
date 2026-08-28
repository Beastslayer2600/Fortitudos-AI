export function Mark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      fill="none"
    >
      <path
        d="M16 2.5 28 8.2v15.6L16 29.5 4 23.8V8.2L16 2.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M11 20.5V11.5h10M16 11.5v9"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="square"
      />
    </svg>
  );
}
