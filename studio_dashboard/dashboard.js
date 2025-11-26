import { runFlowPipeline } from "./api/flow.js";

document.getElementById("run").addEventListener("click", async () => {
    const title = document.getElementById("title").value;
    const plan  = document.getElementById("plan").value;

    const out = await runFlowPipeline(title, plan);

    document.getElementById("promptResult").innerText = JSON.stringify(
        {
            main_prompt: out.main_prompt,
            teaser_prompt: out.teaser_prompt
        },
        null,
        2
    );

    document.getElementById("flowResult").innerText = JSON.stringify(
        out.flow,
        null,
        2
    );
});