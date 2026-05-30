import { useCallback, useRef, useState } from "react";
import { syllabusStreamUrl } from "@/lib/api";

/**
 * Consumes the SSE syllabus stream endpoint and exposes:
 *   { modules, streaming, error, start, reset }
 *
 * Each `module` event is appended to `modules` in real time so the UI
 * can render the syllabus token-by-token (well, module-by-module).
 */
export default function useSyllabusStream() {
    const [modules, setModules] = useState([]);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState(null);
    const sourceRef = useRef(null);

    const reset = useCallback(() => {
        if (sourceRef.current) {
            sourceRef.current.close();
            sourceRef.current = null;
        }
        setModules([]);
        setError(null);
        setStreaming(false);
    }, []);

    const start = useCallback(
        (signalId, { onDone } = {}) =>
            new Promise((resolve, reject) => {
                if (sourceRef.current) sourceRef.current.close();
                setModules([]);
                setError(null);
                setStreaming(true);

                const es = new EventSource(syllabusStreamUrl(signalId));
                sourceRef.current = es;

                es.addEventListener("module", (e) => {
                    try {
                        const m = JSON.parse(e.data);
                        setModules((prev) => [...prev, m]);
                    } catch {
                        /* noop */
                    }
                });
                es.addEventListener("done", (e) => {
                    setStreaming(false);
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
                    es.close();
                    sourceRef.current = null;
                    reject(new Error(msg));
                });
            }),
        []
    );

    return { modules, streaming, error, start, reset };
}
