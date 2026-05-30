import { useCallback, useEffect, useRef, useState } from "react";
import { syllabusStreamUrl } from "@/lib/api";

/**
 * Consumes the SSE syllabus stream endpoint and exposes:
 *   { modules, streaming, error, phase, elapsedS, start, reset }
 *
 * Each `module` event is appended to `modules` in real time so the UI
 * can render the syllabus token-by-token (well, module-by-module).
 * `progress` events drive the `phase` + `elapsedS` indicators while
 * Claude is synthesizing the syllabus.
 */
export default function useSyllabusStream() {
    const [modules, setModules] = useState([]);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState(null);
    const [phase, setPhase] = useState(null);
    const [elapsedS, setElapsedS] = useState(0);
    const sourceRef = useRef(null);

    const reset = useCallback(() => {
        if (sourceRef.current) {
            sourceRef.current.close();
            sourceRef.current = null;
        }
        setModules([]);
        setError(null);
        setStreaming(false);
        setPhase(null);
        setElapsedS(0);
    }, []);

    // Defensive cleanup on unmount — closes any open EventSource.
    useEffect(() => {
        return () => {
            if (sourceRef.current) {
                sourceRef.current.close();
                sourceRef.current = null;
            }
        };
    }, []);

    const start = useCallback(
        (signalId, { onDone } = {}) =>
            new Promise((resolve, reject) => {
                if (sourceRef.current) sourceRef.current.close();
                setModules([]);
                setError(null);
                setStreaming(true);
                setPhase("connecting");
                setElapsedS(0);

                const es = new EventSource(syllabusStreamUrl(signalId));
                sourceRef.current = es;

                es.addEventListener("start", () => {
                    setPhase("synthesizing");
                });
                es.addEventListener("progress", (e) => {
                    try {
                        const p = JSON.parse(e.data);
                        if (p.phase) setPhase(p.phase);
                        if (typeof p.elapsed_s === "number") setElapsedS(p.elapsed_s);
                    } catch {
                        /* noop */
                    }
                });
                es.addEventListener("module", (e) => {
                    try {
                        const m = JSON.parse(e.data);
                        setModules((prev) => [...prev, m]);
                        setPhase("streaming");
                    } catch {
                        /* noop */
                    }
                });
                es.addEventListener("done", (e) => {
                    setStreaming(false);
                    setPhase("done");
                    es.close();
                    sourceRef.current = null;
                    if (onDone) onDone();
                    resolve(e?.data);
                });
                es.addEventListener("error", (e) => {
                    setStreaming(false);
                    const msg =
                        (e?.data && (() => {
                            try {
                                return JSON.parse(e.data).error;
                            } catch {
                                return null;
                            }
                        })()) ||
                        "stream error";
                    setError(msg);
                    setPhase("error");
                    es.close();
                    sourceRef.current = null;
                    reject(new Error(msg));
                });
            }),
        []
    );

    return { modules, streaming, error, phase, elapsedS, start, reset };
}