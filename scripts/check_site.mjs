import assert from "node:assert/strict";
import fs from "node:fs";

const packageJson = JSON.parse(fs.readFileSync("package.json", "utf8"));
const html = fs.readFileSync("site/index.html", "utf8");
const robots = fs.readFileSync("site/robots.txt", "utf8");
const sitemap = fs.readFileSync("site/sitemap.xml", "utf8");
const llms = fs.readFileSync("site/llms.txt", "utf8");
const canonical = "https://sickn33.github.io/tidal-mcp/";

assert.match(html, /<html lang="en">/);
assert.equal((html.match(/<h1(?:\s|>)/g) || []).length, 1, "site must contain exactly one h1");
assert.ok(html.includes(`<link rel="canonical" href="${canonical}">`), "canonical URL is missing");
assert.ok(html.includes(`content="${canonical}"`), "social metadata URL is missing");
assert.ok(html.includes(`@sickn33/tidal-mcp@${packageJson.version}`), "install version is stale");
assert.ok(html.includes("September 4, 2026"), "dated comparison qualifier is missing");
assert.ok(!html.match(/TODO|PLACEHOLDER|example\.com/i), "site contains placeholder content");

const description = html.match(/<meta name="description" content="([^"]+)">/)?.[1];
assert.ok(description, "meta description is missing");
assert.ok(description.length >= 120 && description.length <= 160, "meta description must be 120-160 characters");

const structuredDataText = html.match(
  /<script type="application\/ld\+json">\s*([\s\S]*?)\s*<\/script>/
)?.[1];
assert.ok(structuredDataText, "JSON-LD structured data is missing");
const structuredData = JSON.parse(structuredDataText);
assert.equal(structuredData["@context"], "https://schema.org");
assert.ok(structuredData["@graph"].some((item) => item["@type"] === "SoftwareSourceCode"));
assert.ok(structuredData["@graph"].some((item) => item["@type"] === "FAQPage"));

const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]));
for (const match of html.matchAll(/href="#([^"]+)"/g)) {
  assert.ok(ids.has(match[1]), `internal link points to missing #${match[1]}`);
}

assert.ok(robots.includes(`Sitemap: ${canonical}sitemap.xml`));
assert.ok(sitemap.includes(`<loc>${canonical}</loc>`));
assert.ok(llms.includes(`Version: ${packageJson.version}`));
assert.ok(llms.includes("https://github.com/sickn33/tidal-mcp"));

console.log(`Landing page metadata and links are valid for TIDAL MCP ${packageJson.version}.`);
