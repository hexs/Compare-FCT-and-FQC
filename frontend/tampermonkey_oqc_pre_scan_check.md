# คู่มือการติดตั้งและเปิดใช้งาน Tampermonkey (OQC Pre-Scan Check)

เอกสารนี้สรุปขั้นตอนการติดตั้งส่วนขยาย **Tampermonkey** บน Google Chrome การเปิดสิทธิ์ที่จำเป็น และการเพิ่มสคริปต์สำหรับตรวจสอบ Part (`10.87.1.188:50005`) ก่อนบันทึกการสแกนบนหน้าเว็บ OQC Scan (`10.87.1.231`)

---

## 1. การติดตั้ง Tampermonkey บน Google Chrome

1. เปิด Google Chrome แล้วเข้าไปที่ **Chrome Web Store**
2. ค้นหาคำว่า **Tampermonkey**
3. กดปุ่ม **เพิ่มใน Chrome (Add to Chrome)** และกดยืนยัน **เพิ่มส่วนขยาย (Add extension)**
4. *(แนะนำ)* คลิกไอคอน **รูปจิ๊กซอว์ (Extensions)** มุมขวาบนของ Chrome แล้วกดปักหมุด 📌 ที่ **Tampermonkey** เพื่อให้เห็นสถานะการทำงานได้ง่าย

---

## 2. การเปิดสิทธิ์ Allow User Scripts (จำเป็นสำหรับ Chrome รุ่นใหม่)

หากไม่เปิดสิทธิ์นี้ Tampermonkey จะไม่สามารถรันสคริปต์บนหน้าเว็บได้ (และจะขึ้นแถบสีฟ้าแจ้งเตือน `Please enable the 'Allow User Scripts' extension setting`)

1. พิมพ์ `chrome://extensions` ในช่อง URL ของ Chrome แล้วกด **Enter**
2. เปิดสวิตช์ **โหมดนักพัฒนาซอฟต์แวร์ (Developer mode)** ที่มุมขวาบนให้เป็นสีฟ้า
3. ค้นหาการ์ด **Tampermonkey** แล้วกดปุ่ม **รายละเอียด (Details)** *(หรือคลิกขวาที่ไอคอน Tampermonkey มุมขวาบน > จัดการส่วนขยาย)*
4. เลื่อนลงมาหาหัวข้อ **Allow User Scripts** (อนุญาตสคริปต์ผู้ใช้) แล้วเปิดสวิตช์ให้เป็นสีฟ้า

---

## 3. การเพิ่มสคริปต์ OQC Pre-Scan Check

1. คลิกที่ไอคอน **Tampermonkey** มุมขวาบนของ Chrome
2. เลือกเมนู **Create a new script...** (สร้างสคริปต์ใหม่)
3. ลบโค้ดเริ่มต้นในหน้า Editor ออกให้หมด แล้ววางโค้ดด้านล่างนี้ลงไป:

```javascript
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

        const jobCard = document.querySelector(".card.p-3.mb-3.shadow-sm");
        if (!jobCard) return null;

        box = document.createElement("div");
        box.id = "oqc-stale-warning";
        box.className = "alert alert-warning fw-bold mb-3";
        box.style.display = "none";

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

    function startLastUpdateMonitor() {
        checkLastUpdate();
        setInterval(checkLastUpdate, 60000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startLastUpdateMonitor);
    } else {
        startLastUpdateMonitor();
    }

    console.log("[OQC Check] Script v1.2 โหลดสำเร็จแล้ว!");
})();
```

4. กดบันทึกโดยไปที่เมนู **File > Save** หรือกดคีย์ลัด **`Ctrl + S`**

---

## 4. การตรวจสอบและเริ่มใช้งาน

1. เปิดหน้าเว็บ OQC Scan (เช่น `http://10.87.1.231/OQC/Scan/749`) แล้วกดรีเฟรช (**F5**)
2. สังเกตที่ไอคอน Tampermonkey มุมขวาบน ต้องมี **เลข `1` สีแดง** ปรากฏขึ้น แสดงว่าสคริปต์กำลังทำงานบนหน้านี้อยู่
3. *(หากต้องการเช็กละเอียด)* กด `F12` เปิดแท็บ **Console** จะต้องเห็นข้อความ `[OQC Check] Script v1.2 โหลดสำเร็จแล้ว!`
4. เมื่อเปิดหน้าเว็บหรือสแกนครั้งแรก หาก Tampermonkey เด้งหน้าต่างขออนุญาตเชื่อมต่อไปยัง `10.87.1.188` ให้กดปุ่ม **Always allow domain** (อนุญาตโดเมนนี้เสมอ)

---

## 5. การทำงานของระบบและการแจ้งเตือน

* **ก่อนบันทึกการสแกน (`/OQC/AddScan`):** สคริปต์จะส่ง Serial Number ไปเช็กที่ `http://10.87.1.188:50005/api/pass/{serial}` ก่อน
  * ถ้า `passed` เป็น `true`: ระบบจะบันทึกการสแกนตามปกติ
  * ถ้า `passed` ไม่ใช่ `true`: ระบบจะเด้ง Alert แจ้งข้อความจาก Server และล้างช่องสแกนอัตโนมัติโดยไม่ส่งข้อมูลไปบันทึก
* **การตรวจสอบความสดใหม่ของข้อมูล (ทุก 60 วินาที):** สคริปต์จะเช็ก `http://10.87.1.188:50005/api/last-update`
  * **แถบสีเหลือง:** แจ้งเตือนเมื่อ `last_scan.age_seconds > 60` วินาที พร้อมแสดงเวลาอัปเดตล่าสุด (จะหายไปเองเมื่อข้อมูลกลับมาอัปเดตปกติ)
  * **แถบสีแดง:** แจ้งเตือนเมื่อไม่สามารถติดต่อ Server `10.87.1.188:50005` ได้

---

## 6. การแก้ปัญหาเบื้องต้น (Troubleshooting)

| อาการที่พบ | สาเหตุที่เป็นไปได้ | วิธีแก้ไข |
| :--- | :--- | :--- |
| ไม่มีเลข `1` สีแดงที่ไอคอน Tampermonkey | ยังไม่ได้เปิด `Allow User Scripts` หรือปิดสคริปต์ไว้ | ทำตาม **ข้อ 2** และเช็กในเมนู Tampermonkey ว่าสวิตช์ `Enabled` และ `OQC Pre-Scan Check` เปิดเป็นสีเขียวแล้ว จากนั้นกด `F5` |
| สแกนตัวที่ไม่ผ่านแล้วระบบยัง Add ได้ | สคริปต์ยังไม่ทำงาน หรือเปิดหน้าเว็บค้างไว้ก่อนเซฟสคริปต์ | กด `F5` รีเฟรชหน้าเว็บ และเช็กใน Console ว่ามีข้อความ `[OQC Check] Script v1.2 โหลดสำเร็จแล้ว!` หรือไม่ |
| ขึ้นข้อความเชื่อมต่อ Server ไม่ได้ | เครื่อง `10.87.1.188:50005` ปิดอยู่ หรือเน็ตเวิร์กมีปัญหา | ลองเปิดลิงก์ `http://10.87.1.188:50005/api/last-update` บนเบราว์เซอร์โดยตรงเพื่อตรวจสอบสถานะ Server |