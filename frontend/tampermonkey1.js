
// ==UserScript==
// @name         OQC Pre-Scan Check
// @namespace    http://tampermonkey.net/
// @version      1.1
// @match        *://10.87.1.231/OQC/*
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      10.87.1.188
// @run-at       document-start
// ==/UserScript==

(function () {
    'use strict';

    const originalFetch = unsafeWindow.fetch.bind(unsafeWindow);

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

    console.log("[OQC Check] Script โหลดสำเร็จแล้ว!");
})();