import { useId } from "react";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

/**
 * Accessible field wrappers: label ↔ control ↔ hint wired with ids,
 * every control ≥ 44px tall, 16px font (no mobile focus zoom).
 */

interface FieldChrome {
  label: string;
  hint?: string;
  required?: boolean;
}

interface TextInputProps
  extends FieldChrome,
    Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {}

export function TextInput({
  label,
  hint,
  required,
  className,
  ...input
}: TextInputProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      <input
        id={id}
        className={["field__control", className].filter(Boolean).join(" ")}
        aria-describedby={hintId}
        aria-required={required || undefined}
        required={required}
        {...input}
      />
    </div>
  );
}

interface SelectOption {
  value: string;
  label: string;
}

interface SelectFieldProps
  extends FieldChrome,
    Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  options: SelectOption[];
  placeholder?: string;
}

export function SelectField({
  label,
  hint,
  required,
  options,
  placeholder,
  ...select
}: SelectFieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      <select
        id={id}
        className="field__control"
        aria-describedby={hintId}
        required={required}
        {...select}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

interface TextareaFieldProps
  extends FieldChrome,
    Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {}

export function TextareaField({
  label,
  hint,
  required,
  ...textarea
}: TextareaFieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      <textarea
        id={id}
        className="field__control"
        aria-describedby={hintId}
        required={required}
        {...textarea}
      />
    </div>
  );
}

interface ChoiceGroupProps {
  legend: string;
  hint?: string;
  children: ReactNode;
  columns?: boolean;
}

export function ChoiceGroup({
  legend,
  hint,
  children,
  columns = false,
}: ChoiceGroupProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <fieldset className="fieldset" aria-describedby={hintId}>
      <legend className="fieldset__legend">{legend}</legend>
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      <div className={columns ? "choice-grid choice-grid--two" : "choice-grid"}>
        {children}
      </div>
    </fieldset>
  );
}

interface ChoiceProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "id"> {
  label: string;
  type: "radio" | "checkbox";
}

/** Whole label is the touch target (≥ 44px row). */
export function Choice({ label, type, ...input }: ChoiceProps) {
  return (
    <label className="choice">
      <input type={type} {...input} />
      <span>{label}</span>
    </label>
  );
}
