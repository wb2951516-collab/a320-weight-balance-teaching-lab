const fs = require("fs");
const h = fs.readFileSync(
  "D:/AI-coding/XiaomiMiMoProjects/配载教学建模/output/配载平衡交互教学.html",
  "utf8"
);
const s = h.split("<script>")[1] || "";
let b = 0;
for (const c of s) {
  if (c === "{") b++;
  if (c === "}") b--;
}
console.log("brace", b);
console.log("bw fix", h.includes("sx(slot.st1)-sx(slot.st0)"));
console.log("cabH44", h.includes("cabH:44"));
console.log("fuel100", h.includes("fuelHMax:100"));
console.log("canvas600", h.includes('height="600"'));
