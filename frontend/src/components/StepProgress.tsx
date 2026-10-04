interface StepProgressProps {
  steps: string[];
  /** Index of the current step (0-based); -1 = nothing active yet. */
  current: number;
}

/** Ordered phase list for the Analysis Progress screen (aria-current="step"). */
export function StepProgress({ steps, current }: StepProgressProps) {
  return (
    <ol className="steps">
      {steps.map((step, index) => (
        <li
          key={step}
          className="step"
          aria-current={index === current ? "step" : undefined}
        >
          <span className="step__index" aria-hidden="true">
            {index + 1}
          </span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}
