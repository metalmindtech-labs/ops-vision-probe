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
        client.post(`/signals/${id}/syllabus`).then((r) => r.data),
    stats: () => client.get("/signals/stats").then((r) => r.data),
    seed: () => client.post("/signals/seed").then((r) => r.data),
};
