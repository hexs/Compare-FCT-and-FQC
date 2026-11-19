// ==UserScript==
// @name         OQC Pre-Scan Check
// @namespace    http://tampermonkey.net/
// @version      1.2
// @match        *://10.87.1.231/OQC/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      10.87.1.188
// @run-at       document-start
// ==/UserScript==

(function () {
    'use strict';

    const originalFetch = unsafeWindow.fetch.bind(unsafeWindow);

    // ======================
    // 1. CHECK PART API
    // ======================
    function checkPartApi(serial) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: "GET",
                url: `http://10.87.1.188:50005/api/pass/${encodeURIComponent(serial)}`,
                onload: function (res) {
                    try {
                        resolve(JSON.parse(res.responseText));
                    } catch (e) {
                        reject("Invalid JSON response");
                    }
                },
                onerror: function () {
                    reject("เชื่อมต่อ Server เช็ก Part ไม่ได้");
                }
            });
        });
    }

    unsafeWindow.fetch = async function (url, options) {
        if (typeof url === "string" && url.includes("/OQC/AddScan") && options?.body) {
            const params = new URLSearchParams(options.body);
            const serial = params.get("serialNumber");

            if (serial) {
                console.log("[OQC Check] กำลังตรวจสอบ:", serial);
                const data = await checkPartApi(serial);
                console.log("[OQC Check] ผลลัพธ์:", data);

                if (data.passed !== true) {
                    return Promise.reject(data.message || "Part NG");
                }
            }
        }
        return originalFetch(url, options);
    };

    // ======================
    // 2. CHECK LAST UPDATE (ทุก 60 วินาที)
    // ======================
    function getOrCreateWarningBox() {
        let box = document.getElementById("oqc-stale-warning");
        if (box) return box;

        // หา card แรกที่มี WorkOrder
        const jobCard = document.querySelector(".card.p-3.mb-3.shadow-sm");
        if (!jobCard) return null;

        box = document.createElement("div");
        box.id = "oqc-stale-warning";
        box.className = "alert alert-warning fw-bold mb-3";
        box.style.display = "none";

        // แทรกไว้บนสุดของ card (ก่อน <h4>WorkOrder: ...</h4>)
        jobCard.prepend(box);
        return box;
    }

    function checkLastUpdate() {
        const box = getOrCreateWarningBox();
        if (!box) return;

        GM_xmlhttpRequest({
            method: "GET",
            url: "http://10.87.1.188:50005/api/last-update",
            onload: function (res) {
                try {
                    const data = JSON.parse(res.responseText);
                    const lastScan = data.last_scan;

                    if (lastScan && lastScan.age_seconds > 60) {
                        box.className = "alert alert-warning fw-bold mb-3";
                        box.innerText = `⚠️ คำเตือน: ข้อมูลถูกอัปเดตล่าสุดเมื่อ ${lastScan.text} (อาจเป็นข้อมูลเก่า กรุณาตรวจสอบระบบ)`;
                        box.style.display = "block";
                    } else {
                        box.style.display = "none";
                    }
                } catch (e) {
                    console.error("[OQC Check] อ่านค่า last-update ไม่ได้:", e);
                }
            },
            onerror: function () {
                box.className = "alert alert-danger fw-bold mb-3";
                box.innerText = "⚠️ ไม่สามารถเชื่อมต่อ Server เช็กสถานะการอัปเดตข้อมูลได้ (10.87.1.188:50005)";
                box.style.display = "block";
            }
        });
    }

    // รอให้หน้าเว็บโหลด DOM เสร็จก่อนเริ่มเช็ก
    function startLastUpdateMonitor() {
        checkLastUpdate();
        setInterval(checkLastUpdate, 10000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startLastUpdateMonitor);
    } else {
        startLastUpdateMonitor();
    }

    console.log("[OQC Check] Script v1.2 โหลดสำเร็จแล้ว!");
})();