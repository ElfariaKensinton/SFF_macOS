// LumaCore — Steam client hook layer for SteaMidra.
// Copyright (c) 2025-2026 Midrag (https://github.com/Midrags).
// Distributed under the GNU General Public License v3 or later.
// See <https://www.gnu.org/licenses/> for the full license text.

// dwmapi.dll HiJack Project

#include <windows.h>
#include <cstring>

#pragma comment(linker, "/EXPORT:DllCanUnloadNow=c:\\windows\\system32\\dwmapi.DllCanUnloadNow,@111")
#pragma comment(linker, "/EXPORT:DllGetClassObject=c:\\windows\\system32\\dwmapi.DllGetClassObject,@115")
#pragma comment(linker, "/EXPORT:DwmAttachMilContent=c:\\windows\\system32\\dwmapi.DwmAttachMilContent,@116")
#pragma comment(linker, "/EXPORT:DwmDefWindowProc=c:\\windows\\system32\\dwmapi.DwmDefWindowProc,@117")
#pragma comment(linker, "/EXPORT:DwmDetachMilContent=c:\\windows\\system32\\dwmapi.DwmDetachMilContent,@118")
#pragma comment(linker, "/EXPORT:DwmEnableBlurBehindWindow=c:\\windows\\system32\\dwmapi.DwmEnableBlurBehindWindow,@119")
#pragma comment(linker, "/EXPORT:DwmEnableComposition=c:\\windows\\system32\\dwmapi.DwmEnableComposition,@102")
#pragma comment(linker, "/EXPORT:DwmEnableMMCSS=c:\\windows\\system32\\dwmapi.DwmEnableMMCSS,@120")
#pragma comment(linker, "/EXPORT:DwmExtendFrameIntoClientArea=c:\\windows\\system32\\dwmapi.DwmExtendFrameIntoClientArea,@121")
#pragma comment(linker, "/EXPORT:DwmFlush=c:\\windows\\system32\\dwmapi.DwmFlush,@122")
#pragma comment(linker, "/EXPORT:DwmGetColorizationColor=c:\\windows\\system32\\dwmapi.DwmGetColorizationColor,@123")
#pragma comment(linker, "/EXPORT:DwmGetCompositionTimingInfo=c:\\windows\\system32\\dwmapi.DwmGetCompositionTimingInfo,@125")
#pragma comment(linker, "/EXPORT:DwmGetGraphicsStreamClient=c:\\windows\\system32\\dwmapi.DwmGetGraphicsStreamClient,@126")
#pragma comment(linker, "/EXPORT:DwmGetGraphicsStreamTransformHint=c:\\windows\\system32\\dwmapi.DwmGetGraphicsStreamTransformHint,@129")
#pragma comment(linker, "/EXPORT:DwmGetTransportAttributes=c:\\windows\\system32\\dwmapi.DwmGetTransportAttributes,@130")
#pragma comment(linker, "/EXPORT:DwmGetUnmetTabRequirements=c:\\windows\\system32\\dwmapi.DwmGetUnmetTabRequirements,@133")
#pragma comment(linker, "/EXPORT:DwmGetWindowAttribute=c:\\windows\\system32\\dwmapi.DwmGetWindowAttribute,@134")
#pragma comment(linker, "/EXPORT:DwmInvalidateIconicBitmaps=c:\\windows\\system32\\dwmapi.DwmInvalidateIconicBitmaps,@149")
#pragma comment(linker, "/EXPORT:DwmIsCompositionEnabled=c:\\windows\\system32\\dwmapi.DwmIsCompositionEnabled,@188")
#pragma comment(linker, "/EXPORT:DwmModifyPreviousDxFrameDuration=c:\\windows\\system32\\dwmapi.DwmModifyPreviousDxFrameDuration,@189")
#pragma comment(linker, "/EXPORT:DwmQueryThumbnailSourceSize=c:\\windows\\system32\\dwmapi.DwmQueryThumbnailSourceSize,@190")
#pragma comment(linker, "/EXPORT:DwmRegisterThumbnail=c:\\windows\\system32\\dwmapi.DwmRegisterThumbnail,@191")
#pragma comment(linker, "/EXPORT:DwmRenderGesture=c:\\windows\\system32\\dwmapi.DwmRenderGesture,@192")
#pragma comment(linker, "/EXPORT:DwmSetDxFrameDuration=c:\\windows\\system32\\dwmapi.DwmSetDxFrameDuration,@193")
#pragma comment(linker, "/EXPORT:DwmSetIconicLivePreviewBitmap=c:\\windows\\system32\\dwmapi.DwmSetIconicLivePreviewBitmap,@194")
#pragma comment(linker, "/EXPORT:DwmSetIconicThumbnail=c:\\windows\\system32\\dwmapi.DwmSetIconicThumbnail,@195")
#pragma comment(linker, "/EXPORT:DwmSetPresentParameters=c:\\windows\\system32\\dwmapi.DwmSetPresentParameters,@196")
#pragma comment(linker, "/EXPORT:DwmSetWindowAttribute=c:\\windows\\system32\\dwmapi.DwmSetWindowAttribute,@197")
#pragma comment(linker, "/EXPORT:DwmShowContact=c:\\windows\\system32\\dwmapi.DwmShowContact,@198")
#pragma comment(linker, "/EXPORT:DwmTetherContact=c:\\windows\\system32\\dwmapi.DwmTetherContact,@199")
#pragma comment(linker, "/EXPORT:DwmTetherTextContact=c:\\windows\\system32\\dwmapi.DwmTetherTextContact,@156")
#pragma comment(linker, "/EXPORT:DwmTransitionOwnedWindow=c:\\windows\\system32\\dwmapi.DwmTransitionOwnedWindow,@200")
#pragma comment(linker, "/EXPORT:DwmUnregisterThumbnail=c:\\windows\\system32\\dwmapi.DwmUnregisterThumbnail,@201")
#pragma comment(linker, "/EXPORT:DwmUpdateThumbnailProperties=c:\\windows\\system32\\dwmapi.DwmUpdateThumbnailProperties,@202")
#pragma comment(linker, "/EXPORT:DwmpAllocateSecurityDescriptor=c:\\windows\\system32\\dwmapi.DwmpAllocateSecurityDescriptor,@136")
#pragma comment(linker, "/EXPORT:DwmpDxGetWindowSharedSurface=c:\\windows\\system32\\dwmapi.DwmpDxGetWindowSharedSurface,@100")
#pragma comment(linker, "/EXPORT:DwmpDxUpdateWindowSharedSurface=c:\\windows\\system32\\dwmapi.DwmpDxUpdateWindowSharedSurface,@101")
#pragma comment(linker, "/EXPORT:DwmpDxgiIsThreadDesktopComposited=c:\\windows\\system32\\dwmapi.DwmpDxgiIsThreadDesktopComposited,@128")
#pragma comment(linker, "/EXPORT:DwmpEnableDDASupport=c:\\windows\\system32\\dwmapi.DwmpEnableDDASupport,@143")
#pragma comment(linker, "/EXPORT:DwmpFreeSecurityDescriptor=c:\\windows\\system32\\dwmapi.DwmpFreeSecurityDescriptor,@137")
#pragma comment(linker, "/EXPORT:DwmpGetColorizationParameters=c:\\windows\\system32\\dwmapi.DwmpGetColorizationParameters,@127")
#pragma comment(linker, "/EXPORT:DwmpRenderFlick=c:\\windows\\system32\\dwmapi.DwmpRenderFlick,@135")
#pragma comment(linker, "/EXPORT:DwmpSetColorizationParameters=c:\\windows\\system32\\dwmapi.DwmpSetColorizationParameters,@131")
#pragma comment(linker, "/EXPORT:DwmpUpdateProxyWindowForCapture=c:\\windows\\system32\\dwmapi.DwmpUpdateProxyWindowForCapture,@183")
#pragma comment(linker, "/EXPORT:#103=c:\\windows\\system32\\dwmapi.#103,@103,NONAME")
#pragma comment(linker, "/EXPORT:#104=c:\\windows\\system32\\dwmapi.#104,@104,NONAME")
#pragma comment(linker, "/EXPORT:#105=c:\\windows\\system32\\dwmapi.#105,@105,NONAME")
#pragma comment(linker, "/EXPORT:#106=c:\\windows\\system32\\dwmapi.#106,@106,NONAME")
#pragma comment(linker, "/EXPORT:#107=c:\\windows\\system32\\dwmapi.#107,@107,NONAME")
#pragma comment(linker, "/EXPORT:#108=c:\\windows\\system32\\dwmapi.#108,@108,NONAME")
#pragma comment(linker, "/EXPORT:#109=c:\\windows\\system32\\dwmapi.#109,@109,NONAME")
#pragma comment(linker, "/EXPORT:#110=c:\\windows\\system32\\dwmapi.#110,@110,NONAME")
#pragma comment(linker, "/EXPORT:#112=c:\\windows\\system32\\dwmapi.#112,@112,NONAME")
#pragma comment(linker, "/EXPORT:#113=c:\\windows\\system32\\dwmapi.#113,@113,NONAME")
#pragma comment(linker, "/EXPORT:#114=c:\\windows\\system32\\dwmapi.#114,@114,NONAME")
#pragma comment(linker, "/EXPORT:#124=c:\\windows\\system32\\dwmapi.#124,@124,NONAME")
#pragma comment(linker, "/EXPORT:#132=c:\\windows\\system32\\dwmapi.#132,@132,NONAME")
#pragma comment(linker, "/EXPORT:#138=c:\\windows\\system32\\dwmapi.#138,@138,NONAME")
#pragma comment(linker, "/EXPORT:#139=c:\\windows\\system32\\dwmapi.#139,@139,NONAME")
#pragma comment(linker, "/EXPORT:#140=c:\\windows\\system32\\dwmapi.#140,@140,NONAME")
#pragma comment(linker, "/EXPORT:#141=c:\\windows\\system32\\dwmapi.#141,@141,NONAME")
#pragma comment(linker, "/EXPORT:#142=c:\\windows\\system32\\dwmapi.#142,@142,NONAME")
#pragma comment(linker, "/EXPORT:#144=c:\\windows\\system32\\dwmapi.#144,@144,NONAME")
#pragma comment(linker, "/EXPORT:#145=c:\\windows\\system32\\dwmapi.#145,@145,NONAME")
#pragma comment(linker, "/EXPORT:#146=c:\\windows\\system32\\dwmapi.#146,@146,NONAME")
#pragma comment(linker, "/EXPORT:#147=c:\\windows\\system32\\dwmapi.#147,@147,NONAME")
#pragma comment(linker, "/EXPORT:#148=c:\\windows\\system32\\dwmapi.#148,@148,NONAME")
#pragma comment(linker, "/EXPORT:#150=c:\\windows\\system32\\dwmapi.#150,@150,NONAME")
#pragma comment(linker, "/EXPORT:#151=c:\\windows\\system32\\dwmapi.#151,@151,NONAME")
#pragma comment(linker, "/EXPORT:#152=c:\\windows\\system32\\dwmapi.#152,@152,NONAME")
#pragma comment(linker, "/EXPORT:#153=c:\\windows\\system32\\dwmapi.#153,@153,NONAME")
#pragma comment(linker, "/EXPORT:#154=c:\\windows\\system32\\dwmapi.#154,@154,NONAME")
#pragma comment(linker, "/EXPORT:#155=c:\\windows\\system32\\dwmapi.#155,@155,NONAME")
#pragma comment(linker, "/EXPORT:#157=c:\\windows\\system32\\dwmapi.#157,@157,NONAME")
#pragma comment(linker, "/EXPORT:#158=c:\\windows\\system32\\dwmapi.#158,@158,NONAME")
#pragma comment(linker, "/EXPORT:#159=c:\\windows\\system32\\dwmapi.#159,@159,NONAME")
#pragma comment(linker, "/EXPORT:#160=c:\\windows\\system32\\dwmapi.#160,@160,NONAME")
#pragma comment(linker, "/EXPORT:#161=c:\\windows\\system32\\dwmapi.#161,@161,NONAME")
#pragma comment(linker, "/EXPORT:#162=c:\\windows\\system32\\dwmapi.#162,@162,NONAME")
#pragma comment(linker, "/EXPORT:#163=c:\\windows\\system32\\dwmapi.#163,@163,NONAME")
#pragma comment(linker, "/EXPORT:#164=c:\\windows\\system32\\dwmapi.#164,@164,NONAME")
#pragma comment(linker, "/EXPORT:#165=c:\\windows\\system32\\dwmapi.#165,@165,NONAME")
#pragma comment(linker, "/EXPORT:#166=c:\\windows\\system32\\dwmapi.#166,@166,NONAME")
#pragma comment(linker, "/EXPORT:#167=c:\\windows\\system32\\dwmapi.#167,@167,NONAME")
#pragma comment(linker, "/EXPORT:#168=c:\\windows\\system32\\dwmapi.#168,@168,NONAME")
#pragma comment(linker, "/EXPORT:#169=c:\\windows\\system32\\dwmapi.#169,@169,NONAME")
#pragma comment(linker, "/EXPORT:#170=c:\\windows\\system32\\dwmapi.#170,@170,NONAME")
#pragma comment(linker, "/EXPORT:#171=c:\\windows\\system32\\dwmapi.#171,@171,NONAME")
#pragma comment(linker, "/EXPORT:#172=c:\\windows\\system32\\dwmapi.#172,@172,NONAME")
#pragma comment(linker, "/EXPORT:#173=c:\\windows\\system32\\dwmapi.#173,@173,NONAME")
#pragma comment(linker, "/EXPORT:#174=c:\\windows\\system32\\dwmapi.#174,@174,NONAME")
#pragma comment(linker, "/EXPORT:#175=c:\\windows\\system32\\dwmapi.#175,@175,NONAME")
#pragma comment(linker, "/EXPORT:#176=c:\\windows\\system32\\dwmapi.#176,@176,NONAME")
#pragma comment(linker, "/EXPORT:#177=c:\\windows\\system32\\dwmapi.#177,@177,NONAME")
#pragma comment(linker, "/EXPORT:#178=c:\\windows\\system32\\dwmapi.#178,@178,NONAME")
#pragma comment(linker, "/EXPORT:#179=c:\\windows\\system32\\dwmapi.#179,@179,NONAME")
#pragma comment(linker, "/EXPORT:#180=c:\\windows\\system32\\dwmapi.#180,@180,NONAME")
#pragma comment(linker, "/EXPORT:#181=c:\\windows\\system32\\dwmapi.#181,@181,NONAME")
#pragma comment(linker, "/EXPORT:#182=c:\\windows\\system32\\dwmapi.#182,@182,NONAME")
#pragma comment(linker, "/EXPORT:#184=c:\\windows\\system32\\dwmapi.#184,@184,NONAME")
#pragma comment(linker, "/EXPORT:#185=c:\\windows\\system32\\dwmapi.#185,@185,NONAME")
#pragma comment(linker, "/EXPORT:#186=c:\\windows\\system32\\dwmapi.#186,@186,NONAME")
#pragma comment(linker, "/EXPORT:#187=c:\\windows\\system32\\dwmapi.#187,@187,NONAME")

DWORD WINAPI InjectLumaCore(LPVOID lpParam)
{
    char exePath[MAX_PATH];
    if (GetModuleFileNameA(NULL, exePath, MAX_PATH))
    {
        const char* exeName = strrchr(exePath, '\\');
        exeName = exeName ? exeName + 1 : exePath;
        if (_stricmp(exeName, "steam.exe") == 0)
        {
            LoadLibraryA("LumaCore.dll");
        }
    }
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD dwReason, PVOID pvReserved)
{
    if (dwReason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule);
        CreateThread(NULL, 0, InjectLumaCore, NULL, 0, NULL);
    }
    return TRUE;
}
