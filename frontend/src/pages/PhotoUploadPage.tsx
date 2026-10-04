import { useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, uploadImage } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { SelectField } from "../components/FormField";
import { useAssessment } from "../hooks/useAssessment";
import { useConfig } from "../hooks/useConfig";
import type { QualityVerdict, ViewType } from "../types/backend";

const VIEW_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "symptom_closeup", label: "Symptom close-up (preferred)" },
  { value: "field_context", label: "Field context" },
  { value: "whole_plant", label: "Whole plant" },
  { value: "healthy_comparison", label: "Healthy comparison" },
];

type UploadStatus = "staged" | "uploading" | "uploaded" | "failed";

interface StagedPhoto {
  id: string;
  file: File;
  viewType: ViewType;
  status: UploadStatus;
  quality: QualityVerdict | null;
  error: string | null;
}

/**
 * Photo upload — 0–4 JPEG/PNG images, each with its own view type.
 * Photos are optional: "Continue to Analysis" never depends on Vision.
 */
export function PhotoUploadPage() {
  const navigate = useNavigate();
  const { assessment, recordUpload } = useAssessment();
  const { config } = useConfig();

  const maxPhotos = config?.max_photos ?? 4;
  const maxBytes = config?.photo_limit_bytes ?? 8 * 1024 * 1024;

  const [photos, setPhotos] = useState<StagedPhoto[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    setNotice(null);
    const selected = event.target.files;
    if (!selected || selected.length === 0) return;

    const accepted: StagedPhoto[] = [];
    const rejected: string[] = [];
    for (const file of Array.from(selected)) {
      if (photos.length + accepted.length >= maxPhotos) {
        rejected.push(`Only ${maxPhotos} photos per check.`);
        break;
      }
      if (file.type !== "image/jpeg" && file.type !== "image/png") {
        rejected.push(`${file.name}: JPEG or PNG only.`);
        continue;
      }
      if (file.size > maxBytes) {
        rejected.push(
          `${file.name}: larger than ${Math.round(maxBytes / (1024 * 1024))} MB.`,
        );
        continue;
      }
      accepted.push({
        id: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
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
    event.target.value = "";
  }

  function setViewType(id: string, viewType: ViewType) {
    setPhotos((current) =>
      current.map((photo) =>
        photo.id === id ? { ...photo, viewType } : photo,
      ),
    );
  }

  function removePhoto(id: string) {
    setPhotos((current) => current.filter((photo) => photo.id !== id));
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
          cause instanceof ApiError
            ? cause.message
            : "Upload failed. Try again.";
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
    <div className="stack">
      <h1>Photos</h1>
      <p className="page-intro">
        Add a sharp, well-lit close-up of an affected leaf — JPEG or PNG, up to{" "}
        {maxPhotos} photos. Photos are optional: you can continue without
        Vision.
      </p>

      {notice ? <Alert>{notice}</Alert> : null}

      <Card title="Choose photos">
        <div className="field">
          <label className="field__label" htmlFor="photo-input">
            Photos
          </label>
          <input
            id="photo-input"
            className="file-input"
            type="file"
            accept="image/jpeg,image/png"
            multiple
            onChange={handleFiles}
          />
        </div>
        {photos.length === 0 ? (
          <p className="empty-note">
            No photos selected — that is OK. You can continue to analysis.
          </p>
        ) : (
          <ul className="upload-list">
            {photos.map((photo) => (
              <li key={photo.id} className="upload-row">
                <div className="upload-row__head">
                  <span className="upload-row__name">{photo.file.name}</span>
                  <span className="card__meta">
                    {Math.max(1, Math.round(photo.file.size / 1024))} KB
                  </span>
                </div>
                <SelectField
                  label="Photo type"
                  options={VIEW_OPTIONS}
                  value={photo.viewType}
                  disabled={photo.status !== "staged"}
                  onChange={(event) =>
                    setViewType(photo.id, event.target.value as ViewType)
                  }
                />
                {photo.status === "staged" ? (
                  <p className="empty-note">Ready to upload.</p>
                ) : null}
                {photo.status === "uploading" ? (
                  <p className="empty-note">Uploading…</p>
                ) : null}
                {photo.status === "failed" ? (
                  <Alert>{photo.error ?? "Upload failed."}</Alert>
                ) : null}
                {photo.status === "uploaded" && photo.quality ? (
                  photo.quality.passed ? (
                    <p className="quality-pass">
                      Quality check passed. Uploaded.
                    </p>
                  ) : (
                    <div className="quality-fail">
                      <p style={{ margin: 0 }}>
                        Quality check failed — Vision may not read this photo.
                      </p>
                      {photo.quality.issues.length > 0 ? (
                        <p className="empty-note" style={{ margin: 0 }}>
                          {photo.quality.issues.join(" · ")}
                        </p>
                      ) : null}
                      <p className="empty-note" style={{ margin: 0 }}>
                        Retake: fill the frame with the affected leaf, hold
                        steady, use daylight, avoid glare.
                      </p>
                    </div>
                  )
                ) : null}
                {photo.status !== "uploading" ? (
                  <Button
                    variant="secondary"
                    onClick={() => removePhoto(photo.id)}
                  >
                    Remove
                  </Button>
                ) : null}
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
              ? "Uploading…"
              : `Upload ${stagedCount} photo${stagedCount > 1 ? "s" : ""}`}
          </Button>
        ) : null}
        {uploadedCount > 0 ? (
          <p className="empty-note" style={{ marginBlockStart: "var(--space-2)" }}>
            {uploadedCount} photo{uploadedCount > 1 ? "s" : ""} uploaded.
          </p>
        ) : null}
      </Card>

      <div className="stack">
        <Button block onClick={() => navigate("/analysis")}>
          Continue to Analysis
        </Button>
        <LinkButton to="/farm-details" variant="secondary" block>
          Back
        </LinkButton>
      </div>
    </div>
  );
}
