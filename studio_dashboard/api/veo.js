import { API } from "./config.js";

export async function generateVeoPrompts(title, plan) {
    const res = await fetch(API.VEO_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, plan })
    });

    return await res.json();
}