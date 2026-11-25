#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <sys/ioctl.h>
#include <unistd.h>
#include <vector>
#include <zlib.h>
#include <libpq-fe.h>

#include "ftxui/component/component.hpp"
#include "ftxui/component/screen_interactive.hpp"
#include "ftxui/dom/elements.hpp"

using namespace ftxui;

struct NeonTask {
  long long id = 0;
  std::string description;
  bool completed = false;
  bool priority = false;
};

namespace {
using PgResult = std::unique_ptr<PGresult, decltype(&PQclear)>;

bool PgCommand(PGconn* connection, const char* sql) {
  PgResult result(PQexec(connection, sql), PQclear);
  if (PQresultStatus(result.get()) == PGRES_COMMAND_OK ||
      PQresultStatus(result.get()) == PGRES_TUPLES_OK)
    return true;
  std::cerr << "PostgreSQL error: " << PQerrorMessage(connection);
  return false;
}

bool SaveTaskOrder(PGconn* connection, const std::vector<NeonTask>& tasks) {
  if (!PgCommand(connection, "BEGIN")) return false;
  for (size_t i = 0; i < tasks.size(); ++i) {
    const auto& task = tasks[i];
    const std::string id = std::to_string(task.id);
    const std::string order = std::to_string(i);
    const char* values[] = {id.c_str(), task.description.c_str(),
                            task.completed ? "true" : "false",
                            task.priority ? "true" : "false", order.c_str()};
    PgResult result(PQexecParams(connection,
        "UPDATE taskman_tasks SET description=$2, completed=$3, priority=$4, sort_order=$5 WHERE id=$1",
        5, nullptr, values, nullptr, nullptr, 0), PQclear);
    if (PQresultStatus(result.get()) != PGRES_COMMAND_OK) {
      std::cerr << "PostgreSQL error: " << PQerrorMessage(connection);
      PgCommand(connection, "ROLLBACK");
      return false;
    }
  }
  return PgCommand(connection, "COMMIT");
}

bool InsertTask(PGconn* connection, NeonTask& task, int order) {
  const std::string sort_order = std::to_string(order);
  const char* values[] = {task.description.c_str(), task.completed ? "true" : "false",
                          task.priority ? "true" : "false", sort_order.c_str()};
  PgResult result(PQexecParams(connection,
      "INSERT INTO taskman_tasks(description, completed, priority, sort_order) VALUES($1,$2,$3,$4) RETURNING id",
      4, nullptr, values, nullptr, nullptr, 0), PQclear);
  if (PQresultStatus(result.get()) != PGRES_TUPLES_OK) {
    std::cerr << "PostgreSQL error: " << PQerrorMessage(connection);
    return false;
  }
  task.id = std::stoll(PQgetvalue(result.get(), 0, 0));
  return true;
}

bool DeleteTask(PGconn* connection, long long id) {
  const std::string value = std::to_string(id);
  const char* values[] = {value.c_str()};
  PgResult result(PQexecParams(connection, "DELETE FROM taskman_tasks WHERE id=$1",
                               1, nullptr, values, nullptr, nullptr, 0), PQclear);
  if (PQresultStatus(result.get()) == PGRES_COMMAND_OK) return true;
  std::cerr << "PostgreSQL error: " << PQerrorMessage(connection);
  return false;
}
}  // namespace

namespace {
constexpr int kImageWidth = 480;
constexpr int kImageHeight = 240;
constexpr int kFrameCount = 18;
constexpr int kImageId = 725031;
constexpr int kLogoImageId = kImageId + 2;

std::string Base64(const std::vector<unsigned char>& bytes) {
  constexpr char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string result;
  result.reserve((bytes.size() + 2) / 3 * 4);
  for (size_t i = 0; i < bytes.size(); i += 3) {
    const unsigned int a = bytes[i];
    const unsigned int b = i + 1 < bytes.size() ? bytes[i + 1] : 0;
    const unsigned int c = i + 2 < bytes.size() ? bytes[i + 2] : 0;
    const unsigned int value = (a << 16) | (b << 8) | c;
    result += alphabet[(value >> 18) & 63];
    result += alphabet[(value >> 12) & 63];
    result += i + 1 < bytes.size() ? alphabet[(value >> 6) & 63] : '=';
    result += i + 2 < bytes.size() ? alphabet[value & 63] : '=';
  }
  return result;
}

std::string KittyCommand(const std::string& parameters, const std::string& data = {}) {
  return "\x1b_G" + parameters + (data.empty() ? "" : ";" + data) + "\x1b\\";
}

bool SupportsKittyGraphics() {
  const char* term = std::getenv("TERM");
  return std::getenv("KITTY_WINDOW_ID") != nullptr ||
         (term != nullptr && std::string(term).find("kitty") != std::string::npos);
}

std::vector<unsigned char> NeonFrame(int frame, int width, int height) {
  std::vector<unsigned char> rgba(width * height * 4, 0);
  const double phase = static_cast<double>(frame) / kFrameCount * 6.283185307179586;
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const double left = 10, right = width - 11;
      const double top = 10, bottom = height - 11;
      double distance = 1e9;
      if (x >= left && x <= right) {
        distance = std::min(std::abs(y - top), std::abs(y - bottom));
      }
      if (y >= top && y <= bottom) {
        distance = std::min(distance, std::min(std::abs(x - left), std::abs(x - right)));
      }
      const double pulse = 0.78 + 0.22 * std::sin(phase + (x + y) * 0.018);
      const double glow = std::exp(-(distance * distance) / 38.0) * pulse;
      const double core = std::exp(-(distance * distance) / 1.1) * pulse;
      const size_t at = (static_cast<size_t>(y) * width + x) * 4;
      rgba[at] = static_cast<unsigned char>(std::min(255.0, 155 * glow + 235 * core));
      rgba[at + 1] = static_cast<unsigned char>(std::min(255.0, 24 * glow + 205 * core));
      rgba[at + 2] = static_cast<unsigned char>(std::min(255.0, 255 * glow));
      rgba[at + 3] = static_cast<unsigned char>(std::min(255.0, 150 * glow + 105 * core));
    }
  }
  return rgba;
}

std::string KittyFramePacket(int frame, int image_id = kImageId,
                             int width = kImageWidth, int height = kImageHeight) {
  const auto pixels = NeonFrame(frame, width, height);
  uLongf compressed_size = compressBound(pixels.size());
  std::vector<unsigned char> compressed(compressed_size);
  if (compress2(compressed.data(), &compressed_size, pixels.data(), pixels.size(), 1) != Z_OK)
    return {};
  compressed.resize(compressed_size);
  const std::string payload = Base64(compressed);
  const size_t chunk_size = 4096;
  std::string packet;
  for (size_t offset = 0; offset < payload.size(); offset += chunk_size) {
    const size_t length = std::min(chunk_size, payload.size() - offset);
    const bool more = offset + length < payload.size();
    const std::string header = offset == 0
        ? (frame == 0 ? "a=t" : "a=f") + std::string(",f=32,s=") +
              std::to_string(width) + ",v=" + std::to_string(height) +
              ",i=" + std::to_string(image_id) + ",o=z,z=83,q=2,m=" + (more ? "1" : "0")
        : std::string("q=2,m=") + (more ? "1" : "0");
    packet += KittyCommand(header, payload.substr(offset, length));
  }
  return packet;
}

void StartKittyNeon(int columns, int rows) {
  if (!isatty(STDOUT_FILENO) || !SupportsKittyGraphics()) return;
  std::string packets = KittyCommand("a=d,d=I,i=" + std::to_string(kImageId) + ",q=2");
  for (int frame = 0; frame < kFrameCount; ++frame)
    packets += KittyFramePacket(frame);
  packets += KittyCommand("a=a,i=" + std::to_string(kImageId) + ",r=1,z=83,q=2");
  packets += KittyCommand("a=a,i=" + std::to_string(kImageId) + ",s=3,v=1,q=2");
  packets += "\0337\033[H" + KittyCommand("a=p,i=" + std::to_string(kImageId) +
      ",p=1,c=" + std::to_string(columns) + ",r=" + std::to_string(rows) + ",z=1,C=1,q=2") + "\0338";
  std::cout << packets << std::flush;
}

void StopKittyNeon() {
  if (SupportsKittyGraphics())
    std::cout << KittyCommand("a=d,d=I,i=" + std::to_string(kImageId) + ",q=2")
              << KittyCommand("a=d,d=I,i=" + std::to_string(kImageId + 1) + ",q=2")
              << KittyCommand("a=d,d=I,i=" + std::to_string(kLogoImageId) + ",q=2") << std::flush;
}

void PlaceTaskmanLogo(int columns, int row) {
  if (!isatty(STDOUT_FILENO) || !SupportsKittyGraphics()) return;
  static bool uploaded = false;
  std::string packets;
  if (!uploaded) {
    const char* configured_logo = std::getenv("TASKMAN_LOGO_PATH");
    const std::string logo_path = configured_logo ? configured_logo : TASKMAN_LOGO_PATH;
    std::ifstream file(logo_path, std::ios::binary);
    if (!file) {
      std::cerr << "Could not open Taskman logo: " << logo_path << '\n';
      return;
    }
    std::vector<unsigned char> png((std::istreambuf_iterator<char>(file)),
                                   std::istreambuf_iterator<char>());
    const std::string payload = Base64(png);
    constexpr size_t chunk_size = 4096;
    for (size_t offset = 0; offset < payload.size(); offset += chunk_size) {
      const size_t length = std::min(chunk_size, payload.size() - offset);
      const bool more = offset + length < payload.size();
      const std::string header = offset == 0
          ? "a=t,f=100,t=d,i=" + std::to_string(kLogoImageId) + ",q=2,m=" + (more ? "1" : "0")
          : std::string("q=2,m=") + (more ? "1" : "0");
      packets += KittyCommand(header, payload.substr(offset, length));
    }
    uploaded = true;
  }
  constexpr int logo_columns = 26;
  constexpr int logo_rows = 7;
  if (columns < logo_columns + 16) return;
  const int left = columns - 4 - logo_columns + 1;
  packets += "\0337\033[" + std::to_string(row) + ";" + std::to_string(left) + "H";
  packets += KittyCommand("a=p,i=" + std::to_string(kLogoImageId) + ",p=1,c=" +
      std::to_string(logo_columns) + ",r=" + std::to_string(logo_rows) + ",z=2,C=1,q=2") + "\0338";
  std::cout << packets << std::flush;
}

void ShowHelpNeon(int columns, int rows, bool show) {
  constexpr int help_image_id = kImageId + 1;
  if (!isatty(STDOUT_FILENO)) return;
  if (!SupportsKittyGraphics()) return;
  if (!show) {
    std::cout << KittyCommand("a=d,d=I,i=" + std::to_string(help_image_id) + ",q=2") << std::flush;
    return;
  }
  const int width = std::min(44, columns - 10);
  const int height = std::min(18, rows - 6);
  if (width < 20 || height < 8) return;
  std::string packets = KittyCommand("a=d,d=I,i=" + std::to_string(help_image_id) + ",q=2");
  constexpr int help_pixel_width = 320;
  constexpr int help_pixel_height = 320;
  for (int frame = 0; frame < kFrameCount; ++frame)
    packets += KittyFramePacket(frame, help_image_id, help_pixel_width, help_pixel_height);
  packets += KittyCommand("a=a,i=" + std::to_string(help_image_id) + ",r=1,z=83,q=2");
  packets += KittyCommand("a=a,i=" + std::to_string(help_image_id) + ",s=3,v=1,q=2");
  const int left = (columns - width) / 2 + 1;
  const int top = (rows - height) / 2 + 1;
  packets += "\0337\033[" + std::to_string(top) + ";" + std::to_string(left) + "H";
  packets += KittyCommand("a=p,i=" + std::to_string(help_image_id) + ",p=1,c=" +
      std::to_string(width) + ",r=" + std::to_string(height) + ",z=2,C=1,q=2") + "\0338";
  std::cout << packets << std::flush;
}
}  // namespace

int main() {
  const char* connection_info = std::getenv("TASKMAN_DATABASE_URL");
  PGconn* raw_connection = PQconnectdb(connection_info ? connection_info : "dbname=taskman");
  std::unique_ptr<PGconn, decltype(&PQfinish)> database(raw_connection, PQfinish);
  if (PQstatus(database.get()) != CONNECTION_OK) {
    std::cerr << "Cannot connect to Taskman PostgreSQL database: "
              << PQerrorMessage(database.get())
              << "Set TASKMAN_DATABASE_URL or create a local taskman database.\n";
    return 1;
  }
  if (!PgCommand(database.get(),
      "CREATE TABLE IF NOT EXISTS taskman_tasks ("
      "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
      "description TEXT NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE, "
      "priority BOOLEAN NOT NULL DEFAULT FALSE, sort_order BIGINT NOT NULL)"))
    return 1;
  if (!PgCommand(database.get(),
      "CREATE TABLE IF NOT EXISTS taskman_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))
    return 1;
  if (!PgCommand(database.get(),
      "INSERT INTO taskman_settings(key, value) VALUES('mock_seeded', 'false') ON CONFLICT (key) DO NOTHING"))
    return 1;

  std::vector<NeonTask> tasks;
  {
    PgResult result(PQexec(database.get(),
        "SELECT id, description, completed, priority FROM taskman_tasks ORDER BY sort_order, id"), PQclear);
    if (PQresultStatus(result.get()) != PGRES_TUPLES_OK) {
      std::cerr << "PostgreSQL error: " << PQerrorMessage(database.get());
      return 1;
    }
    for (int row = 0; row < PQntuples(result.get()); ++row) {
      tasks.push_back({std::stoll(PQgetvalue(result.get(), row, 0)), PQgetvalue(result.get(), row, 1),
                       std::string(PQgetvalue(result.get(), row, 2)) == "t",
                       std::string(PQgetvalue(result.get(), row, 3)) == "t"});
    }
  }
  PgResult seed_state(PQexec(database.get(),
      "SELECT value FROM taskman_settings WHERE key='mock_seeded'"), PQclear);
  if (PQresultStatus(seed_state.get()) != PGRES_TUPLES_OK) {
    std::cerr << "PostgreSQL error: " << PQerrorMessage(database.get());
    return 1;
  }
  const bool should_seed = std::string(PQgetvalue(seed_state.get(), 0, 0)) == "false";
  if (tasks.empty() && should_seed) {
    tasks = {{0, "Review project roadmap", false, true},
             {0, "Organize development notes", false, false},
             {0, "Prepare release checklist", true, false},
             {0, "Update terminal colors", false, true}};
    for (size_t i = 0; i < tasks.size(); ++i)
      if (!InsertTask(database.get(), tasks[i], static_cast<int>(i))) return 1;
  }
  if (should_seed && !PgCommand(database.get(),
      "UPDATE taskman_settings SET value='true' WHERE key='mock_seeded'"))
    return 1;
  int selected = 0;
  bool entering_task = false;
  bool editing_task = false;
  bool light_theme = false;
  bool help_open = false;
  int terminal_columns = 0;
  int terminal_rows = 0;
  std::string draft;
  std::string message;
  bool kitty_graphics_started = false;
  int logo_columns = 0;
  int logo_rows = 0;
  auto screen = ScreenInteractive::Fullscreen();

  auto input = Input(&draft, "Task description");
  auto renderer = Renderer(input, [&] {
    if (!kitty_graphics_started) {
      winsize size{};
      if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &size) == 0) {
        terminal_columns = size.ws_col;
        terminal_rows = size.ws_row;
        StartKittyNeon(size.ws_col, size.ws_row);
        logo_columns = size.ws_col;
        logo_rows = size.ws_row;
        PlaceTaskmanLogo(logo_columns, 4);
      }
      kitty_graphics_started = true;
    }
    winsize current_size{};
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &current_size) == 0 &&
        (current_size.ws_col != logo_columns || current_size.ws_row != logo_rows)) {
      terminal_columns = current_size.ws_col;
      terminal_rows = current_size.ws_row;
      logo_columns = current_size.ws_col;
      logo_rows = current_size.ws_row;
      PlaceTaskmanLogo(logo_columns, 4);
    }
    Elements rows;
    rows.push_back(text("  +  Create a new task") | color(Color::Magenta));
    for (size_t i = 0; i < tasks.size(); ++i) {
      const auto& task = tasks[i];
      const std::string indicator = task.completed ? "✓" : "·";
      const std::string star = task.priority ? " ★" : "";
      auto description = text(task.description);
      if (task.completed)
        description = description | color(Color::GrayDark) | bgcolor(Color::Black);
      else if (task.priority)
        description = description | color(Color::RGB(0, 255, 0));
      else
        description = description | color(light_theme ? Color::RGB(30, 25, 40) : Color::White);
      auto priority_star = text(star) | color(Color::Yellow);
      auto row = hbox(Elements{text("  " + indicator + " ") |
                                   color(task.completed ? Color::GrayDark : Color::GrayLight),
                               description, priority_star});
      if (task.completed)
        row = row | bgcolor(Color::Black);
      rows.push_back(std::move(row));
    }
    for (size_t i = 0; i < rows.size(); ++i) {
      if (static_cast<int>(i) == selected)
        rows[i] = rows[i] | bgcolor(light_theme ? Color::RGB(220, 210, 235) : Color::RGB(48, 24, 72)) |
                  color(light_theme ? Color::RGB(25, 20, 35) : Color::White);
    }

    auto list = vbox({text("  TASKS  /  IN-MEMORY") | bold | color(Color::RGB(190, 100, 255)),
                       separator(), vbox(std::move(rows))}) |
                border | color(Color::RGB(145, 65, 255));
    auto logo = text("") | size(WIDTH, EQUAL, 26) | size(HEIGHT, EQUAL, 7);
    auto header = hbox({text(" TASKMAN NEON") | bold | color(Color::RGB(220, 65, 255)),
                        filler(), logo});
    auto content = hbox({list | flex, filler()});
    auto footer = text(" ↑/↓ Navigate   h Help ") |
                  color(Color::RGB(100, 180, 255));
    auto inset = [](Element content) {
      return vbox({text(""), text(""), text(""),
                   hbox({text("    "), content | flex, text("    ")}) | flex});
    };
    if (entering_task) {
      auto dialog = vbox({text(editing_task ? "Edit task" : "Create task") | bold | color(Color::Magenta),
                          input->Render(), text("Enter saves · Escape cancels")}) |
                    border | color(Color::Cyan);
      return inset(vbox({header, separator(), filler(), dialog | center, filler(), footer})) |
             bgcolor(light_theme ? Color::White : Color::RGB(8, 6, 14));
    }
    auto page = inset(vbox({header, separator(), content | flex,
                            text(message) | color(light_theme ? Color::RGB(130, 80, 0) : Color::Yellow),
                            separator(), footer})) | bgcolor(light_theme ? Color::White : Color::RGB(8, 6, 14));
    if (help_open) {
      auto help = vbox({text(" TASKMAN  /  KEYBOARD SHORTCUTS ") | bold | color(Color::RGB(220, 65, 255)),
                        separator(), text("↑ / ↓       Select a task"),
                        text("Ctrl+↑ / ↓ Move selected task"), text("Enter       Activate selection"),
                        text("n           Create task"), text("e           Edit selected task"),
                        text("d           Delete selected task"), text("c           Toggle completion"),
                        text("p           Toggle priority"), text("m           Toggle light theme"),
                        text("q           Quit"), separator(),
                        text("Press h or Esc to close") | color(Color::Cyan)}) |
                   size(WIDTH, LESS_THAN, 58) | border | color(Color::RGB(185, 65, 255));
      const int panel_width = std::max(24, std::min(42, terminal_columns - 12));
      return dbox({page, help | size(WIDTH, EQUAL, panel_width) | center});
    }
    return page;
  });

  auto component = CatchEvent(renderer, [&](Event event) {
    if (help_open) {
      if (event == Event::Character('h') || event == Event::Escape) {
        help_open = false;
        ShowHelpNeon(terminal_columns, terminal_rows, false);
      }
      return true;
    }
    if (entering_task) {
      if (event == Event::Escape) {
        entering_task = false;
        editing_task = false;
        draft.clear();
        return true;
      }
      if (event == Event::Return) {
        if (draft.find_first_not_of(" \t\r\n") == std::string::npos) {
          message = "Description cannot be empty.";
        } else {
          if (editing_task) {
            tasks[static_cast<size_t>(selected - 1)].description = draft;
            message = "Task updated.";
          } else {
            NeonTask new_task{0, draft, false, false};
            if (!InsertTask(database.get(), new_task, static_cast<int>(tasks.size()))) {
              message = "Task could not be saved.";
              return true;
            }
            tasks.push_back(std::move(new_task));
            selected = static_cast<int>(tasks.size());
            message = "Task added.";
          }
          SaveTaskOrder(database.get(), tasks);
          entering_task = false;
          editing_task = false;
          draft.clear();
        }
        return true;
      }
      return false;
    }
    if (event == Event::ArrowUp) { selected = std::max(0, selected - 1); return true; }
    if (event == Event::ArrowDown) { selected = std::min(static_cast<int>(tasks.size()), selected + 1); return true; }
    if (event == Event::Character('h')) {
      help_open = true;
      ShowHelpNeon(terminal_columns, terminal_rows, true);
      return true;
    }
    if (event == Event::Character('m')) { light_theme = !light_theme; return true; }
    if (event == Event::Character('q')) { screen.Exit(); return true; }
    if (event == Event::Character('n') || (event == Event::Return && selected == 0)) {
      entering_task = true;
      editing_task = false;
      draft.clear();
      input->TakeFocus();
      message.clear();
      return true;
    }
    if (selected > 0 && selected <= static_cast<int>(tasks.size())) {
      auto& task = tasks[static_cast<size_t>(selected - 1)];
      if (event == Event::ArrowUpCtrl && selected > 1) {
        std::swap(tasks[static_cast<size_t>(selected - 1)], tasks[static_cast<size_t>(selected - 2)]);
        --selected;
        SaveTaskOrder(database.get(), tasks);
        return true;
      }
      if (event == Event::ArrowDownCtrl && selected < static_cast<int>(tasks.size())) {
        std::swap(tasks[static_cast<size_t>(selected - 1)], tasks[static_cast<size_t>(selected)]);
        ++selected;
        SaveTaskOrder(database.get(), tasks);
        return true;
      }
      if (event == Event::Character('e')) {
        entering_task = true;
        editing_task = true;
        draft = task.description;
        input->TakeFocus();
        message.clear();
        return true;
      }
      if (event == Event::Character('c')) { task.completed = !task.completed; SaveTaskOrder(database.get(), tasks); return true; }
      if (event == Event::Character('p')) { task.priority = !task.priority; SaveTaskOrder(database.get(), tasks); return true; }
      if (event == Event::Character('d')) {
        const long long deleted_id = task.id;
        if (!DeleteTask(database.get(), deleted_id)) return true;
        tasks.erase(tasks.begin() + (selected - 1));
        selected = std::min(selected, static_cast<int>(tasks.size()));
        SaveTaskOrder(database.get(), tasks);
        message = "Task deleted.";
        return true;
      }
      if (event == Event::Return) { message = task.description; return true; }
    }
    return false;
  });
  screen.Loop(component);
  StopKittyNeon();
  return 0;
}
