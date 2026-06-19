import { SectionHead } from "../Hairline";
import { useMlflowState } from "../../hooks/useMlflowState";
import type { MlflowModel } from "../../lib/types";

/**
 * Model Registry instrument — the live link to Node-3 MLflow.
 *
 * Surfaces registry STATUS (is the registry reachable, which models carry a
 * @production alias, at what version) and RESULTS (the held-out eval metrics
 * logged on the @production run: precision@k, F1, false-alarm rate). The
 * @production alias is exactly what the UUV edge nodes (the Pis) load, so this
 * panel is the ground truth for "what model is deployed to the fleet, and how
 * good is it." Proxied through GET /api/mlflow — the browser can't reach
 * MLflow's REST API directly.
 */
export function MlflowPanel() {
  const { mlflow, conn } = useMlflowState();
  const live = conn === "live";
  const dot =
    conn === "live" ? "var(--nominal)" : conn === "stale" ? "var(--caution)" : "var(--muted)";
  const label =
    conn === "live" ? "LIVE" : conn === "stale" ? "STALE" : conn === "connecting" ? "LINKING" : "OFFLINE";

  return (
    <section style={{ display: "flex", flexDirection: "column" }}>
      <SectionHead index="D" title="Model Registry" meta="MLflow · T&E" />
      <div style={{ padding: "12px 15px", flex: 1 }}>
        {/* registry connection status */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 11 }}>
          <span style={{ width: 8, height: 8, background: dot, borderRadius: 1 }} />
          <span className="display" style={{ fontSize: 11, fontWeight: 700, color: dot, letterSpacing: "0.06em" }}>
            {label}
          </span>
          <span className="mono" style={{ marginLeft: "auto", fontSize: 9, color: "var(--muted)", letterSpacing: "0.01em" }}>
            {mlflow?.tracking_uri?.replace(/^https?:\/\//, "") ?? "—"}
          </span>
        </div>

        {live && mlflow && mlflow.models.length > 0 ? (
          mlflow.models.map((m) => <ModelRow key={m.name} model={m} />)
        ) : (
          <div className="mono" style={{ fontSize: 10, color: "var(--muted)", lineHeight: 1.55 }}>
            {conn === "offline" || conn === "stale"
              ? "registry unreachable — bash deploy/mlflow/run.sh (Node-3 :5050)"
              : "linking to the fleet model registry …"}
          </div>
        )}

        <div className="mono" style={{ fontSize: 9, color: "var(--muted)", lineHeight: 1.55, marginTop: 11, letterSpacing: "0.01em" }}>
          The <span style={{ color: "var(--amber)" }}>@production</span> alias is what the UUV edge
          nodes load. Metrics are held-out eval at registration — the accreditation evidence.
        </div>
      </div>
    </section>
  );
}

function ModelRow({ model }: { model: MlflowModel }) {
  const pk = model.metrics?.precision_at_k;
  const f1 = model.metrics?.f1;
  const far = model.metrics?.false_alarm_rate;
  const n = model.metrics?.n_records;
  const hasProd = model.production_version != null;
  const pct = typeof pk === "number" ? Math.max(0, Math.min(1, pk)) * 100 : 0;
  const barColor = typeof pk === "number" && pk >= 0.5 ? "var(--nominal)" : "var(--caution)";

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink)", letterSpacing: "0.01em" }}>
          {model.name}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 9,
            letterSpacing: "0.08em",
            color: hasProd ? "var(--amber)" : "var(--muted)",
            border: `1px solid ${hasProd ? "var(--amber-dim)" : "var(--hair-lit)"}`,
            padding: "2px 7px",
          }}
        >
          {hasProd ? `@production · v${model.production_version}` : "no @production"}
        </span>
      </div>

      {typeof pk === "number" ? (
        <>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 3 }}>
            <span className="eyebrow" style={{ fontSize: 8.5 }}>PRECISION@K</span>
            <span className="num" style={{ fontSize: 12, color: "var(--ink)" }}>{pk.toFixed(2)}</span>
          </div>
          <div style={{ height: 6, background: "var(--hair)", position: "relative" }}>
            <div style={{ position: "absolute", inset: 0, width: `${pct}%`, background: barColor }} />
          </div>
          <div className="mono" style={{ fontSize: 9, color: "var(--ink-dim)", marginTop: 4, letterSpacing: "0.01em" }}>
            {typeof f1 === "number" && <>F1 {f1.toFixed(2)} · </>}
            {typeof far === "number" && <>FAR {far.toFixed(2)} · </>}
            {typeof n === "number" && <>n={n.toFixed(0)}</>}
          </div>
        </>
      ) : (
        <div className="mono" style={{ fontSize: 9, color: "var(--muted)" }}>
          registered · no eval metrics on this version
        </div>
      )}
    </div>
  );
}
