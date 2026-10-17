#!/usr/bin/env node
"use strict";

/**
 * Captures the /skyline page through a 3D -> 2D -> 3D toggle cycle and encodes
 * the frames into assets/skyline-preview.gif for the profile README.
 *
 * Env overrides:
 *   SITE_URL     page to capture (default production /skyline)
 *   OUT_PATH     output gif path
 *   CHROME_PATH  use an existing Chrome/Edge via puppeteer-core (local testing)
 */

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const SITE_URL = process.env.SITE_URL || "https://buildwithanshul.vercel.app/skyline";
const OUT = process.env.OUT_PATH || path.join(__dirname, "..", "..", "assets", "skyline-preview.gif");
const FINAL_FRAMES = 31;
const FPS = 7;
const VIEWPORT = { width: 1100, height: 760 };

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForStableStage(page) {
  const deadline = Date.now() + 10000;
  let last = -1;
  let stable = 0;
  while (Date.now() < deadline) {
    const h = await page.evaluate(() => {
      const btn = document.querySelector('button[aria-label="3D skyline"]');
      const sec = btn && btn.closest("section");
      const canvas = sec && sec.querySelector('canvas[role="img"]');
      return canvas ? Math.round(canvas.parentElement.getBoundingClientRect().height) : -1;
    });
    if (h > 0 && Math.abs(h - last) <= 1) {
      stable += 300;
      if (stable >= 600) return;
    } else {
      stable = 0;
    }
    last = h;
    await sleep(300);
  }
}

async function captureCycle() {
  const execPath = process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH;
  const puppeteer = execPath ? require("puppeteer-core") : require("puppeteer");

  const browser = await puppeteer.launch({
    ...(execPath ? { executablePath: execPath } : {}),
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars"],
    defaultViewport: VIEWPORT,
  });

  const framesDir = fs.mkdtempSync(path.join(os.tmpdir(), "skyline-dense-"));
  const seqDir = fs.mkdtempSync(path.join(os.tmpdir(), "skyline-seq-"));

  try {
    const page = await browser.newPage();
    await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForSelector('button[aria-label="3D skyline"]', { timeout: 30000 });

    // Card-only GIF: hide the fixed nav and footer so they never bleed into
    // the frame below the card when it shrinks during the 2D morph.
    await page.addStyleTag({ content: ".top-nav, footer { display: none !important; }" });

    await Promise.race([
      page.waitForResponse((r) => r.url().includes("/api/contributions"), { timeout: 20000 }).catch(() => null),
      sleep(5000),
    ]);

    await page.evaluate(() => {
      const btn = document.querySelector('button[aria-label="3D skyline"]');
      const sec = btn && btn.closest("section");
      if (sec) {
        const top = sec.getBoundingClientRect().top + window.scrollY;
        window.scrollTo(0, Math.max(0, top - 28));
      }
    });
    await sleep(800);
    await waitForStableStage(page);

    // Fixed clip box around the card only (nav/footer excluded). The box is
    // measured once at full 3D height and reused for every frame — the card
    // only changes height during the morph, and every frame must share
    // dimensions or the ffmpeg image2 sequence stops at the first size change.
    const clip = await page.evaluate(() => {
      const btn = document.querySelector('button[aria-label="3D skyline"]');
      const sec = btn && btn.closest("section");
      if (!sec) return null;
      const b = sec.getBoundingClientRect();
      const pad = 12;
      return {
        x: Math.max(0, Math.round(b.left + window.scrollX - pad)),
        y: Math.max(0, Math.round(b.top + window.scrollY - pad)),
        width: Math.round(b.width + pad * 2),
        height: Math.round(b.height + pad * 2),
      };
    });
    if (!clip || clip.width < 100) throw new Error("card not found for clip box");

    const shots = [];
    const shot = async () => {
      const file = path.join(framesDir, `d${String(shots.length).padStart(3, "0")}.png`);
      await page.screenshot({ path: file, clip, captureBeyondViewport: true });
      shots.push(file);
    };
    const sleepShot = async (ms) => {
      await sleep(ms);
      await shot();
    };

    // Start in 3D (default), morph to 2D, hold, morph back, hold — seamless loop.
    await shot();
    const in3d = await page.$eval('button[aria-label="3D skyline"]', (b) => b.getAttribute("aria-pressed") === "true");
    if (!in3d) {
      await page.click('button[aria-label="3D skyline"]');
      await sleep(1700);
    }

    await sleepShot(250);
    await sleepShot(250);
    await page.click('button[aria-label="Flat heat map"]');
    for (let i = 0; i < 15; i++) await sleepShot(100); // morph to 2D (1300ms) + slack
    for (let i = 0; i < 5; i++) await sleepShot(100); // hold 2D
    await page.click('button[aria-label="3D skyline"]');
    for (let i = 0; i < 15; i++) await sleepShot(100); // morph to 3D + slack
    for (let i = 0; i < 4; i++) await sleepShot(100); // hold 3D tail

    if (shots.length < FINAL_FRAMES) throw new Error(`only ${shots.length} frames captured`);
    console.log(`captured ${shots.length} dense frames`);

    // Evenly pick FINAL_FRAMES across the cycle; first and last are both 3D.
    for (let i = 0; i < FINAL_FRAMES; i++) {
      const idx = Math.round((i * (shots.length - 1)) / (FINAL_FRAMES - 1));
      fs.copyFileSync(shots[idx], path.join(seqDir, `f${String(i + 1).padStart(4, "0")}.png`));
    }
    console.log(`selected ${fs.readdirSync(seqDir).length} frames for encoding`);

    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    const ff = spawnSync(
      "ffmpeg",
      [
        "-y",
        "-framerate", String(FPS),
        "-start_number", "1",
        "-i", path.join(seqDir, "f%04d.png"),
        "-filter_complex", "[0:v]split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
        "-loop", "0",
        OUT,
      ],
      { encoding: "utf8" },
    );
    if (ff.status !== 0) {
      console.error(ff.stderr || ff.stdout);
      throw new Error("ffmpeg failed");
    }

    const size = fs.statSync(OUT).size;
    console.log(`wrote ${OUT} (${(size / 1024).toFixed(0)} KB, ${FINAL_FRAMES} frames @ ${FPS}fps)`);
    if (size > 2 * 1024 * 1024) throw new Error(`GIF too large: ${size} bytes`);
  } finally {
    await browser.close().catch(() => {});
    const keep = process.env.KEEP_TMP === "1";
    for (const dir of [framesDir, seqDir]) {
      if (keep) {
        console.log(`kept ${dir}`);
        continue;
      }
      try {
        fs.rmSync(dir, { recursive: true, force: true });
      } catch (_) {}
    }
  }
}

async function main() {
  let lastErr;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      await captureCycle();
      return;
    } catch (err) {
      lastErr = err;
      console.error(`attempt ${attempt} failed: ${err && err.message}`);
      if (attempt < 2) await sleep(2000);
    }
  }
  throw lastErr;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
