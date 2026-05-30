import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({
    baseURL: API,
    headers: { "Content-Type": "application/json" },
});

export const SignalsAPI = {
    list: () => client.get("/signals").then((r) => r.data),
    get: (id) => client.get(`/signals/${id}`).then((r) => r.data),
    create: (payload) => client.post("/signals", payload).then((r) => r.data),
    update: (id, payload) =>
        client.put(`/signals/${id}`, payload).then((r) => r.data),
    remove: (id) => client.delete(`/signals/${id}`).then((r) => r.data),
    triggerSyllabus: (id) =>
        client.post(`/signals/${id}/syllabus`, null, { timeout: 90000 }).then((r) => r.data),
    stats: () => client.get("/signals/stats").then((r) => r.data),
    seed: () => client.post("/signals/seed").then((r) => r.data),
};

export const ScraperAPI = {
    run: () =>
        client
            .post("/scraper/run", null, { timeout: 180000 })
            .then((r) => r.data),
    ingestHtml: (html) =>
        client
            .post("/scraper/ingest-html", { html }, { timeout: 180000 })
            .then((r) => r.data),
    status: () => client.get("/scraper/status").then((r) => r.data),
    runs: (limit = 10) =>
        client.get(`/scraper/runs?limit=${limit}`).then((r) => r.data),
};

export const PublishAPI = {
    publish: (id) =>
        client
            .post(`/signals/${id}/publish`, null, { timeout: 30000 })
            .then((r) => r.data),
    preview: (id) =>
        client.get(`/signals/${id}/publish/preview`).then((r) => r.data),
    publishAllLive: () =>
        client
            .post(`/signals/publish-all-live`, null, { timeout: 180000 })
            .then((r) => r.data),
    retryPending: () =>
        client
            .post(`/signals/retry-pending-publishes`, null, { timeout: 60000 })
            .then((r) => r.data),
};

export const AlertsAPI = {
    list: (onlyUnack = true) =>
        client
            .get(`/alerts?only_unack=${onlyUnack ? "true" : "false"}`)
            .then((r) => r.data),
    ack: (id) => client.post(`/alerts/${id}/ack`).then((r) => r.data),
    ackAll: () => client.post(`/alerts/ack-all`).then((r) => r.data),
};

export const IntegrationsAPI = {
    status: () => client.get(`/integrations/status`).then((r) => r.data),
    testWhatsApp: () =>
        client
            .post(`/integrations/whatsapp/test`, null, { timeout: 30000 })
            .then((r) => r.data),
    publishSpec: () =>
        client.get(`/integrations/publish-payload-spec`).then((r) => r.data),
    handoffDocUrl: () => `${API}/integrations/handoff-doc`,
    handoffDoc: () =>
        client
            .get(`/integrations/handoff-doc`, { responseType: "text" })
            .then((r) => r.data),
    receiverSpec: () =>
        client.get(`/integrations/webhook-receiver-spec`).then((r) => r.data),
};

export const VelocityAPI = {
    get: ({ hours = 24, limit = 6, ids = null } = {}) =>
        client
            .get(`/signals/velocity`, {
                params: { hours, limit, ...(ids ? { ids } : {}) },
            })
            .then((r) => r.data),
};

export const syllabusStreamUrl = (id) =>
    `${API}/signals/${id}/syllabus/stream`;
