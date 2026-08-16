#include <windows.h>
#include <wchar.h>

static void show_error(const wchar_t *message) {
    MessageBoxW(NULL, message, L"DepthuVideoConverter", MB_OK | MB_ICONERROR);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show_command) {
    wchar_t app_dir[MAX_PATH];
    wchar_t python_path[MAX_PATH];
    wchar_t script_path[MAX_PATH];
    wchar_t process_command[MAX_PATH * 3];
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    wchar_t *separator;

    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show_command;

    if (!GetModuleFileNameW(NULL, app_dir, MAX_PATH)) {
        show_error(L"无法确定应用所在目录。");
        return 1;
    }
    separator = wcsrchr(app_dir, L'\\');
    if (separator == NULL) {
        show_error(L"应用路径无效。");
        return 1;
    }
    *separator = L'\0';

    swprintf(python_path, MAX_PATH, L"%ls\\pythonw.exe", app_dir);
    swprintf(script_path, MAX_PATH, L"%ls\\app\\desktop_launcher.py", app_dir);
    swprintf(process_command, MAX_PATH * 3, L"\"%ls\" \"%ls\"", python_path, script_path);

    startup.cb = sizeof(startup);
    if (!CreateProcessW(
            python_path,
            process_command,
            NULL,
            NULL,
            FALSE,
            CREATE_NO_WINDOW,
            NULL,
            app_dir,
            &startup,
            &process)) {
        show_error(L"无法启动应用。请确认压缩包已完整解压。\n\n不要单独移动 EXE 文件。");
        return 1;
    }

    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
