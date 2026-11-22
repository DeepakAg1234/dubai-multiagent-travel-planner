"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { Footer } from "@/components/site/Footer";
import { Check } from "@/components/site/Icons";
import { Photo } from "@/components/site/Photo";
import { SiteNav } from "@/components/site/SiteNav";
import { altFor, pick } from "@/lib/images";
import { milestoneStates } from "@/lib/milestones";
import { parseSession, saveSession, sessionRaw, subscribeStorage, type Session } from "@/lib/trip";
import type { Snapshot } from "@/lib/types";
import { useTripRun } from "@/lib/use-trip-run";

import { TripResults } from "./TripResults";

function requestFor(session: Session): string {
  if (!session.changes.length) return session.request;
  return `${session.request}\n${session.changes.map((c) => `Change requested: ${c}`).join("\n")}`;
}

export function TripView() {
  const { model, start, cancel } = useTripRun();
  // undefined while server-rendering/hydrating, then the saved trip or null.
  const raw = useSyncExternalStore(subscribeStorage, sessionRaw, () => undefined);
  const session = useMemo(() => (raw === undefined ? undefined : parseSession(raw)), [raw]);
  const [answer, setAnswer] = useState("");
  const [lastGood, setLastGood] = useState<{ snapshot: Snapshot; threadId: string | null; total: number | null } | null>(null);
  const [banner, setBanner] = useState<{ tone: "teal" | "bad"; text: string } | null>(null);
  const started = useRef(false);
  const pendingChange = useRef(false);

  // Start exactly once per page load.
  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    void start(requestFor(session));
  }, [session, start]);

  const snapshot = model.snapshot;
  const plan = snapshot ? snapshot.final ?? snapshot.draft : null;

  // Remember the last finished plan so a failed re-plan never wipes it.
  useEffect(() => {
    if (model.status !== "done" || !snapshot || !plan) return;
    const total = plan.budget?.total_aed ?? snapshot.budget?.total_aed ?? null;
    setLastGood((prev) => {
      if (pendingChange.current) {
        pendingChange.current = false;
        const before = prev?.total;
        if (before != null && total != null) {
          const delta = Math.round(total - before);
          setBanner({
            tone: "teal",
            text:
              delta === 0
                ? "Plan updated. The estimated total is unchanged."
                : `Plan updated. The estimated total moved from AED ${Math.round(before).toLocaleString()} to AED ${Math.round(total).toLocaleString()} (${delta > 0 ? "+" : "\u2212"}AED ${Math.abs(delta).toLocaleString()}).`,
          });
        } else {
          setBanner({ tone: "teal", text: "Plan updated with your change." });
        }
      }
      return { snapshot, threadId: model.threadId, total };
    });
  }, [model.status, snapshot, plan, model.threadId]);

  const onChange = useCallback(
    (text: string) => {
      if (!session) return;
      const next: Session = { ...session, changes: [...session.changes, text] };
      saveSession(next);
      setBanner(null);
      pendingChange.current = true;
      void start(requestFor(next));
    },
    [session, start],
  );

  if (session === undefined) return <Shell><div className="dj-center"><div className="dj-skel" style={{ width: 280, height: 24 }} /></div></Shell>;

  if (session === null) {
    return (
      <Shell>
        <div className="dj-center">
          <div>
            <h1>Let&rsquo;s plan your trip</h1>
            <p className="dj-lede">We don&rsquo;t have any trip details yet. It only takes a minute.</p>
            <Link href="/plan" className="dj-btn">
              Plan My Trip
            </Link>
          </div>
        </div>
      </Shell>
    );
  }

  const running = model.status === "running";
  const hasPlan = Boolean(snapshot && plan && model.status === "done");

  if (model.status === "needs_input") {
    return (
      <Shell>
        <div className="dj-center">
          <form
            className="dj-card"
            style={{ padding: 28, display: "grid", gap: 16, width: "min(520px, 100%)", textAlign: "left" }}
            onSubmit={(e) => {
              e.preventDefault();
              if (answer.trim()) {
                void start(requestFor(session), answer.trim());
                setAnswer("");
              }
            }}
          >
            <span className="dj-eyebrow">One quick question</span>
            <h1 style={{ fontSize: 30 }}>{model.question}</h1>
            <input className="dj-input" value={answer} onChange={(e) => setAnswer(e.target.value)} aria-label="Your answer" autoFocus />
            <button className="dj-btn" type="submit" disabled={!answer.trim()}>
              Continue
            </button>
          </form>
        </div>
      </Shell>
    );
  }

  if (running) {
    return <Progress model={model} onCancel={cancel} revising={Boolean(lastGood)} />;
  }

  // Finished (or failed with an earlier plan still available).
  const show = hasPlan ? { snapshot: snapshot!, threadId: model.threadId } : lastGood && model.status === "error" ? lastGood : null;
  if (show) {
    return (
      <Shell>
        <TripResults
          snapshot={show.snapshot}
          threadId={show.threadId}
          busy={false}
          banner={
            model.status === "error"
              ? { tone: "bad", text: `We couldn\u2019t apply that change (${model.error ?? "the planner stopped"}). Your previous itinerary is shown.` }
              : banner
          }
          changes={session.changes}
          onChange={onChange}
        />
      </Shell>
    );
  }

  if (model.status === "error") {
    return (
      <Shell>
        <div className="dj-center">
          <div>
            <h1>We couldn&rsquo;t finish your itinerary</h1>
            <p className="dj-lede">{model.error ?? "Something went wrong while planning."}</p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
              <button className="dj-btn" type="button" onClick={() => void start(requestFor(session))}>
                Try again
              </button>
              <Link href="/plan" className="dj-btn dj-btn--ghost">
                Edit my trip
              </Link>
            </div>
          </div>
        </div>
      </Shell>
    );
  }

  // Idle after cancel, or done with nothing usable.
  return (
    <Shell>
      <div className="dj-center">
        <div>
          <h1>{model.status === "done" ? "No itinerary came back" : "Planning stopped"}</h1>
          <p className="dj-lede">
            {model.status === "done"
              ? "The planner finished without a usable itinerary. Try adjusting your dates, budget or interests."
              : "You stopped planning. Your answers are saved."}
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
            <button className="dj-btn" type="button" onClick={() => void start(requestFor(session))}>
              Plan again
            </button>
            <Link href="/plan" className="dj-btn dj-btn--ghost">
              Edit my trip
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteNav />
      <main id="main">{children}</main>
      <Footer />
    </>
  );
}

function Progress({ model, onCancel, revising }: { model: ReturnType<typeof useTripRun>["model"]; onCancel: () => void; revising: boolean }) {
  const photo = pick("downtown-dubai", "dubai-marina", "burj-khalifa");
  const steps = milestoneStates(model);
  return (
    <main id="main" className="dj-prog" aria-busy="true">
      <Photo photo={photo} alt={altFor(photo, "Dubai at night")} sizes="100vw" priority label="" />
      <div className="dj-prog-card dj-reveal">
        <span className="dj-eyebrow" style={{ color: "#7fd4d9" }}>
          {revising ? "Updating your itinerary" : "Crafting your itinerary"}
        </span>
        <h1>Building your Dubai trip</h1>
        <p>This can take a minute. We&rsquo;re working through your request step by step.</p>
        <ol className="dj-ms" aria-live="polite">
          {steps.map((s) => (
            <li key={s.id} data-state={s.state}>
              <span className="dj-dot" aria-hidden="true">
                {s.state === "done" ? <Check style={{ color: "#fff" }} /> : null}
              </span>
              <span>
                {s.label}
                <span className="dj-sr">{s.state === "done" ? " (done)" : s.state === "active" ? " (in progress)" : ""}</span>
              </span>
            </li>
          ))}
        </ol>
        <div className="dj-bar" role="progressbar" aria-label="Planning in progress" />
        <div>
          <button type="button" className="dj-btn dj-btn--light dj-btn--sm" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </main>
  );
}
