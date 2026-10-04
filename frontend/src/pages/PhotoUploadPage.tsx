import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, uploadImage } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { useAssessment } from "../hooks/useAssessment";
import { useConfig } from "../hooks/useConfig";
import { translate, useI18n } from "../i18n";
import type { QualityVerdict, ViewType } from "../types/backend";

const VIEW_OPTIONS: ViewType[] = [
  "symptom_closeup",
  "field_context",
  "whole_plant",
  "healthy_comparison",
];

type UploadStatus = "staged" | "uploading" | "uploaded" | "failed";

interface StagedPhoto {
  id: string;
  file: File;
  preview: string;
  viewType: ViewType;
  status: UploadStatus;
  quality: QualityVerdict | null;
  error: string | null;
}

/**
 * Photo upload — 0–4 JPEG/PNG images, each with its own view type.
 * Drag-drop zone + thumbnails. Photos stay optional: "Continue to
 * Analysis" never depends on Vision.
 */
export function PhotoUploadPage() {
  const navigate = useNavigate();
  const { assessment, recordUpload } = useAssessment();
  const { config } = useConfig();
  const { t, locale } = useI18n();

  const maxPhotos = config?.max_photos ?? 4;
  // Vercel request-body limit is ~4.5MB: hard-cap each photo at 4MB client-side
  // (no compression library; a larger photo is rejected with a clear message).
  const maxBytes = Math.min(config?.photo_limit_bytes ?? 8 * 1024 * 1024, 4 * 1024 * 1024);

  const [photos, setPhotos] = useState<StagedPhoto[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const previewsRef = useRef<string[]>([]);

  // Revoke object URLs on unmount (prevents memory leaks).
  useEffect(() => {
    const urls = previewsRef.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  function handleFiles(list: FileList | File[]) {
    setNotice(null);
    const accepted: StagedPhoto[] = [];
    const rejected: string[] = [];
    for (const file of Array.from(list)) {
      if (photos.length + accepted.length >= maxPhotos) {
        rejected.push(t("photo.errMax").replace("{n}", String(maxPhotos)));
        break;
      }
      if (file.type !== "image/jpeg" && file.type !== "image/png") {
        rejected.push(`${file.name}: ${t("photo.errType")}`);
        continue;
      }
      if (file.size > maxBytes) {
        rejected.push(`${file.name}: ${t("photo.errTooLarge")}`);
        continue;
      }
      const preview = URL.createObjectURL(file);
      previewsRef.current.push(preview);
      accepted.push({
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        preview,
        viewType: "symptom_closeup",
        status: "staged",
        quality: null,
        error: null,
      });
    }
    if (rejected.length > 0) setNotice(rejected.join(" "));
    if (accepted.length > 0) {
      setPhotos((current) => [...current, ...accepted]);
    }
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) handleFiles(event.target.files);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files) handleFiles(event.dataTransfer.files);
  }

  function setViewType(id: string, viewType: ViewType) {
    setPhotos((current) =>
      current.map((photo) => (photo.id === id ? { ...photo, viewType } : photo)),
    );
  }

  function removePhoto(id: string) {
    setPhotos((current) => {
      const target = current.find((photo) => photo.id === id);
      if (target) {
        URL.revokeObjectURL(target.preview);
        previewsRef.current = previewsRef.current.filter((u) => u !== target.preview);
      }
      return current.filter((photo) => photo.id !== id);
    });
  }

  async function uploadAll() {
    if (!assessment) return;
    setUploading(true);
    setNotice(null);
    for (const photo of photos) {
      if (photo.status !== "staged") continue;
      setPhotos((current) =>
        current.map((item) =>
          item.id === photo.id ? { ...item, status: "uploading" } : item,
        ),
      );
      try {
        const response = await uploadImage(
          assessment.assessmentId,
          assessment.accessToken,
          photo.file,
          photo.viewType,
        );
        recordUpload({
          name: photo.file.name,
          viewType: photo.viewType,
          imageId: response.image_id,
          qualityPassed: response.quality.passed,
        });
        setPhotos((current) =>
          current.map((item) =>
            item.id === photo.id
              ? { ...item, status: "uploaded", quality: response.quality }
              : item,
          ),
        );
      } catch (cause) {
        const message =
          cause instanceof ApiError ? cause.message : "Upload failed.";
        setPhotos((current) =>
          current.map((item) =>
            item.id === photo.id
              ? { ...item, status: "failed", error: message }
              : item,
          ),
        );
      }
    }
    setUploading(false);
  }

  const stagedCount = photos.filter((p) => p.status === "staged").length;
  const uploadedCount = photos.filter((p) => p.status === "uploaded").length;

  return (
    <div className="page page--photo stack">
      <img
        className="page-tex"
        src="/images/leaf-texture.jpg"
        alt=""
        loading="lazy"
        decoding="async"
        aria-hidden="true"
      />
      <h1 className="page-title">
        {t("photo.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "photo.title")}
          </span>
        ) : null}
      </h1>
      <p className="page-intro">{t("photo.intro")}</p>

      {notice ? <Alert>{notice}</Alert> : null}

      <Card title={t("photo.chooseLabel")}>
        {/* Drag & drop zone (also opens the native picker on tap) */}
        <div
          className={`dropzone${dragging ? " is-dragging" : ""}`}
          role="button"
          tabIndex={0}
          aria-label={t("photo.dropHint")}
          onClick={(event) => {
            // The hidden input's synthesized click bubbles back here —
            // ignore it so we never re-open the picker recursively.
            if (event.target === inputRef.current) return;
            inputRef.current?.click();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <svg
            width="34"
            height="34"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <circle cx="9" cy="10" r="1.6" />
            <path d="m4 17 5-4 4 3 3-2 4 3" />
          </svg>
          <span>{t("photo.dropHint")}</span>
          <input
            ref={inputRef}
            id="photo-input"
            className="visually-hidden"
            type="file"
            accept="image/jpeg,image/png"
            multiple
            tabIndex={-1}
            onChange={onInputChange}
          />
        </div>

        {photos.length === 0 ? (
          <p className="empty-note">📷 {t("photo.empty")}</p>
        ) : (
          <ul className="upload-list">
            {photos.map((photo) => (
              <li key={photo.id} className="upload-row">
                <img
                  className="upload-row__thumb"
                  src={photo.preview}
                  alt=""
                  aria-hidden="true"
                />
                <div className="upload-row__body">
                  <div className="upload-row__head">
                    <span className="upload-row__name">{photo.file.name}</span>
                    <span className="view-badge">
                      {translate(locale, `view.${photo.viewType}`)}
                    </span>
                  </div>
                  <select
                    className="field__control view-select"
                    aria-label={t("photo.typeLabel")}
                    value={photo.viewType}
                    disabled={photo.status !== "staged"}
                    onChange={(event) =>
                      setViewType(photo.id, event.target.value as ViewType)
                    }
                  >
                    {VIEW_OPTIONS.map((view) => (
                      <option key={view} value={view}>
                        {translate(locale, `view.${view}`)}
                      </option>
                    ))}
                  </select>

                  {photo.status === "staged" ? (
                    <p className="empty-note">{t("photo.ready")}</p>
                  ) : null}
                  {photo.status === "uploading" ? (
                    <p className="loading-line">
                      <span className="spinner" aria-hidden="true" />
                      {t("photo.uploading")}
                    </p>
                  ) : null}
                  {photo.status === "failed" ? (
                    <Alert>{photo.error ?? t("photo.fail")}</Alert>
                  ) : null}
                  {photo.status === "uploaded" && photo.quality ? (
                    photo.quality.passed ? (
                      <p className="quality-pass">✅ {t("photo.pass")}</p>
                    ) : (photo.quality.hard_issues?.length ?? 0) > 0 ||
                      !photo.quality.soft_issues ? (
                      <div className="quality-fail">
                        <p style={{ margin: 0 }}>⚠️ {t("photo.fail")}</p>
                        {photo.quality.issues.length > 0 ? (
                          <p className="empty-note" style={{ margin: 0 }}>
                            {photo.quality.issues.join(" · ")}
                          </p>
                        ) : null}
                        <p className="empty-note" style={{ margin: 0 }}>
                          {t("photo.retake")}
                        </p>
                      </div>
                    ) : (
                      <div className="quality-warn">
                        <p style={{ margin: 0 }}>⚠️ {t("photo.softQuality")}</p>
                        <p className="empty-note" style={{ margin: 0 }}>
                          {t("vision.soft.hint")}
                        </p>
                      </div>
                    )
                  ) : null}
                  {photo.status !== "uploading" ? (
                    <Button
                      variant="secondary"
                      onClick={() => removePhoto(photo.id)}
                    >
                      {t("common.remove")}
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}

        {stagedCount > 0 ? (
          <Button
            block
            onClick={uploadAll}
            disabled={uploading}
            style={{ marginBlockStart: "var(--space-3)" }}
          >
            {uploading
              ? t("photo.uploading")
              : t("photo.uploadN").replace("{n}", String(stagedCount))}
          </Button>
        ) : null}
        {uploadedCount > 0 ? (
          <p className="empty-note" style={{ marginBlockStart: "var(--space-2)" }}>
            {t("photo.uploadedN").replace("{n}", String(uploadedCount))}
          </p>
        ) : null}
      </Card>

      <div className="stack">
        <Button block onClick={() => navigate("/analysis")}>
          {t("photo.continue")}
        </Button>
        <LinkButton to="/farm-details" variant="secondary" block>
          {t("common.back")}
        </LinkButton>
      </div>
    </div>
  );
}
