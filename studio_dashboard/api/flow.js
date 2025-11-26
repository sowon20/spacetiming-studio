import { API } from "./config.js";

export async function runFlowPipeline(title, plan) {
    const res = await fetch(API.FLOW_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, plan })
    });

    return await res.json();
}