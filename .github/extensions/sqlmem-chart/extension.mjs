import { createCanvas, CanvasError, joinSession } from "@github/copilot-sdk/extension";
import { createChartCanvasOptions } from "./viewer.mjs";

await joinSession({ canvases: [createCanvas(createChartCanvasOptions(CanvasError))] });
