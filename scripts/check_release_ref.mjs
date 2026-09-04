import fs from "node:fs";

const packageJson = JSON.parse(fs.readFileSync("package.json", "utf8"));
const releaseRef = process.argv[2];
const expectedRef = `v${packageJson.version}`;

if (!releaseRef) {
  console.error(`Missing release tag. Expected ${expectedRef}.`);
  process.exitCode = 1;
} else if (releaseRef !== expectedRef) {
  console.error(
    `Release tag ${releaseRef} does not match ${packageJson.name}@${packageJson.version}; expected ${expectedRef}.`
  );
  process.exitCode = 1;
} else {
  console.log(`Release tag ${releaseRef} matches ${packageJson.name}@${packageJson.version}.`);
}
