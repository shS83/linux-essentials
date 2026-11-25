#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <functional>
#include <cstdint>
#include <limits>
#include <ctime>
#include <iomanip>
#include <fstream>
#include <sstream>
#include <filesystem>

using namespace std;

struct Task {
    uint64_t id = 0;
    string description;
    bool completed = false;
    bool priority = false;
    size_t hash = 0;
    time_t timestamp = 0;
};

struct Status {
    uint64_t id = 0;
    string name;
    time_t timestamp = 0;
};

string formatTimestamp(time_t timestamp) {
    tm timeInfo{};

    localtime_r(&timestamp, &timeInfo);

    stringstream result;
    result << put_time(&timeInfo, "%d.%m.%Y %H:%M:%S");

    return result.str();
}

string escape_json(const string &s) {
    ostringstream o;
    for (auto c = s.cbegin(); c != s.cend(); c++) {
        if (*c == '"' || *c == '\\' || ('\x00' <= *c && *c <= '\x1f')) {
            o << "\\u"
              << hex << setw(4) << setfill('0') << static_cast<int>(*c);
        } else {
            o << *c;
        }
    }
    return o.str();
}

uint64_t getHistoryId(const vector<Status>&stats) {
    return stats.empty() ? 0 : stats.back().id + 1;
}

size_t calculateHash(const Task& task) {
    string content =
        to_string(task.id) + ":" +
        to_string(task.description.size()) + ":" +
        task.description + ":" +
        (task.completed ? "1" : "0");

    return hash<string>{}(content);
}

vector<string> split_str_by_bar(const string& str)
{
    auto result = vector<string>{};
    auto ss = stringstream{str};

    for (string line; getline(ss, line, '|');)
        result.push_back(line);

    return result;
}

vector<Status> readHistory(const string& mainpath) {
    ifstream input(mainpath + "history.txt");
    string line;
    vector<Status> stats;

    while (getline(input, line)) {
        auto values = split_str_by_bar(line);
        if (values.size() != 3) {
            cerr << "Invalid history entry: " << line << endl;
            continue;
        }
        Status stat;
        try {
            stat.id = stoull(values[0]);
            stat.name = values[1];
            stat.timestamp = stoull(values[2]);
        } catch (exception& e)
        {
            cerr << e.what() << endl;
            continue;
        }

        stats.push_back(stat);
    }
    input.close();
    return stats;
}

bool saveHistory(const vector<Status>& history, const string& mainpath) {
    try {
        ofstream output(mainpath + "history.txt");
        if (!output) {
            cerr << "Could not open history.txt\n";
            return false;
        }
        for (const Status& stat : history) {
            output << stat.id << "|" << stat.name << "|" << stat.timestamp << endl;
        }
        output.close();
    } catch (exception& e) {
        cerr << e.what() << endl;
        return false;
    }
    return true;
}

vector<Task> readTasks(vector<Status>& history, const string& mainpath) {
    try {
        string filename = mainpath + "tasks.txt";
        ifstream input(filename);
        string line;
        vector<Task> tasks2;

        while (getline(input, line)) {
            auto values = split_str_by_bar(line);
            if (values.size() != 5) {
                cerr << "Invalid task entry: " << line << endl;
                continue;
            }
            Task homma;
            homma.id = stoull(values[0]);
            homma.description = values[1];
            homma.completed = (stoi(values[2]) ? true : false);
            homma.hash = stoull(values[3]);
            homma.timestamp = stoull(values[4]);
            tasks2.push_back(homma);
        }
        input.close();
        Status stats;
        stats.id = getHistoryId(history);
        stats.name = "READ A TASK FILE";
        stats.timestamp = time(nullptr);
        history.push_back(stats);
        saveHistory(history, mainpath);
        return tasks2;

    } catch (exception& e) {
        cerr << e.what() << endl;
        return {};
    }

}

void addTask(vector<Task>& tasks, const string& description, vector<Status>& history, uint64_t& nextTaskId, const string& mainpath)
{
    Task task;
    task.id = nextTaskId++;
    ofstream output(mainpath + "nextid.txt");
    if (!output) {
        cerr << "Could not open nextid.txt\n";
    } else
    {
        output << nextTaskId;
        output.close();
    }
    task.description = description;
    task.completed = false;
    task.hash = calculateHash(task);
    task.timestamp = time(nullptr);
    tasks.push_back(task);
    Status stats;
    stats.id = getHistoryId(history);
    stats.name = "ADDED A TASK";
    stats.timestamp = time(nullptr);
    history.push_back(stats);
    saveHistory(history, mainpath);
}

bool saveTasks(const vector<Task>& tasks, vector<Status>& history, const string& mainpath) {
    try {
        ofstream output(mainpath + "tasks.txt");
        if (!output) {
            cerr << "Could not open tasks.txt\n";
            return false;
        }
        for (const Task& task : tasks) {
            output << task.id << "|";
            output << task.description << "|";
            output << task.completed << "|";
            output << task.hash << "|";
            output << task.timestamp << endl;
        }
        output.close();
    } catch (exception& e) {
        cerr << e.what() << endl;
        return false;
    }
    Status stats;
    stats.id = getHistoryId(history);
    stats.name = "SAVED A TASK FILE";
    stats.timestamp = time(nullptr);
    history.push_back(stats);
    saveHistory(history, mainpath);
    return true;
}

void listTasks(const vector<Task>&tasks, vector<Status>&history, bool& TIMESTAMP_RESOLVE, const string& mainpath) {
    for (const Task &task : tasks) {
        cout << "Id: " << task.id << endl;
        cout << "Description: " << task.description << endl;
        cout << "Timestamp: " << (TIMESTAMP_RESOLVE ? formatTimestamp(task.timestamp) : to_string(task.timestamp)) << endl;
        cout << "Hash: " << task.hash << endl;
        cout << "Status: " << (task.completed ? "\033[0;92mCOMPLETED\033[0m\n" : "\033[0;91mINCOMPLETE\033[0m\n") << endl;
    }
    Status stats;
    stats.id = getHistoryId(history);
    stats.name = "LISTED TASKS";
    stats.timestamp = time(nullptr);
    history.push_back(stats);
    saveHistory(history, mainpath);
}

bool deleteTask(vector<Task>& tasks, uint64_t id, vector<Status>& history, const string& mainpath) {
    if (erase_if(tasks, [&](const Task& t) {
        return t.id == id;
    })) {
        Status stats;
        stats.id = getHistoryId(history);
        stats.name = "DELETED TASK";
        stats.timestamp = time(nullptr);
        history.push_back(stats);
        saveTasks(tasks, history, mainpath);
        return true;
    }
    return false;
}

bool completeTask(vector<Task>& tasks, uint64_t id, vector<Status>& history, const string& mainpath) {
    for (Task &task : tasks)
    {
        if (task.id == id) {
            task.completed = task.completed ? false : true;
            task.hash = calculateHash(task);
            Status stats;
            stats.id = getHistoryId(history);
            stats.name = "CHANGED STATE OF A TASK";
            stats.timestamp = time(nullptr);
            history.push_back(stats);
            saveTasks(tasks, history, mainpath);
            return true;
        }
    }
    return false;
}

void showStatistics(const vector<Task>& tasks, vector<Status>& history, bool& HISTORY_SHOWN, bool& TIMESTAMP_RESOLVE) {
    cout << "\033[0;94mStatistics\033[0m" << endl;
    size_t taskCount = tasks.size();

    cout << "\033[0;96mTask Count: \033[0;32m" << taskCount << "\033[0m" << endl;
    auto completed = count_if(
        tasks.begin(),
        tasks.end(),
        [](const Task& task) {
            return task.completed;
        }
    );
    cout << "\033[0;92mCompleted tasks: \033[0;32m" << completed << "\033[0m" << endl;
    cout << "\033[0;93mIncomplete tasks: \033[0;32m" << taskCount - completed << "\033[0m" << endl;
    if (HISTORY_SHOWN) {
        cout << endl;
        for (auto it = history.begin(); it != history.end(); ++it) {
            Status& stats = *it;
            if (it == prev(history.end())) {
                cout << "{" << endl;
                cout << "       \"id\": " << stats.id << endl;
                cout << "   \"action\": \"" << stats.name << "\"" << endl;
                if (TIMESTAMP_RESOLVE){
                    cout << "\"timestamp\": \"" << formatTimestamp(stats.timestamp) << "\"" << endl;
                } else
                {
                    cout << "\"timestamp\": " << stats.timestamp << endl;
                }
                cout << "}" << endl << endl;
            } else
            {
                cout << "{" << endl;
                cout << "       \"id\": " << stats.id << endl;
                cout << "   \"action\": \"" << stats.name << "\"" << endl;
                if (TIMESTAMP_RESOLVE){
                    cout << "\"timestamp\": \"" << formatTimestamp(stats.timestamp) << "\"" << endl;
                } else
                {
                    cout << "\"timestamp\": " << stats.timestamp << endl;
                }
                cout << "}," << endl;
            }
        }
    } else {
        cout << "\033[0;95mHistory entries: \033[0;32m" << history.size() << endl << endl;
    }
}

bool saveJSON_tasks(vector<Task>& tasks, uint64_t &nextTaskId, const string& mainpath)
{
    ofstream taskoutput(mainpath + "tasks.json");
    if (!taskoutput) {
        cerr << "Could not open tasks.json\n";
        return false;
    }
    taskoutput << "{" << endl;
    taskoutput << " \"nextTaskId\": " << nextTaskId << ","  << endl;
    taskoutput << " \"tasks\": " << "["  << endl;
    for (auto it = tasks.begin(); it != tasks.end(); ++it)
    {
        Task& task = *it;
        if (it == prev(tasks.end())) {
            taskoutput << "      {" << endl;
            taskoutput << "          \"id\": " << it->id << ","  << endl;
            taskoutput << "          \"description\": \"" << escape_json(it->description) << "\","  << endl;
            taskoutput << "          \"hash\": " << it->hash << ","  << endl;
            taskoutput << "          \"status\": " << (it->completed ? "true": "false") << ","  << endl;
            taskoutput << "          \"timestamp\": " << it->timestamp << endl;
            taskoutput << "      }" << endl;
            } else {
            taskoutput << "      {" << endl;
            taskoutput << "          \"id\": " << it->id << ","  << endl;
            taskoutput << "          \"description\": \"" << escape_json(it->description) << "\","  << endl;
            taskoutput << "          \"hash\": " << it->hash << ","  << endl;
            taskoutput << "          \"status\": " << (it->completed ? "true": "false") << ","  << endl;
            taskoutput << "          \"timestamp\": " << it->timestamp << endl;
            taskoutput << "      }," << endl;
        }
    }
    taskoutput << "  ]" << endl;
    taskoutput << "}" << endl;
    taskoutput.close();
    return true;
}

bool saveJSON_history(vector<Status>& history, const string& mainpath) {
    ofstream output(mainpath + "history.json");
    if (!output) {
        cerr << "Could not open history.json\n";
        return false;
    }
    output << "{" << endl << "    \"history\": [" << endl;
    for (auto it = history.begin(); it != history.end(); ++it) {
        Status& stats = *it;
        if (it == prev(history.end())) {
            output << "         {" << endl;
            output << "                 \"id\": " <<  stats.id << "," << endl;
            output << "             \"action\": " "\"" << stats.name << "\"," << endl;
            output << "          \"timestamp\": " << stats.timestamp << endl;
            output << "         }" << endl;
        } else
        {
            output << "         {" << endl;
            output << "                 \"id\": " << stats.id << "," << endl;
            output << "             \"action\": " "\"" << stats.name << "\"," << endl;
            output << "          \"timestamp\": " << stats.timestamp << endl;
            output << "         }," << endl;
        }
    }
    output << "    ]" << endl;
    output << "}" << endl;
    output.close();
    return true;
}


static void print_screen(bool HISTORY_SHOWN, bool TIMESTAMP_RESOLVE) {
    cout << "\033[0;94m#\033[0;96m~\033[0m TASKMAN v1.06 \033[0;96m~\033[0;94m#\033[0m" << endl << endl;
    cout << "[\033[0;93m1\033[0m] Add Task" << endl;
    cout << "[\033[0;93m2\033[0m] List Tasks" << endl;
    cout << "[\033[0;93m3\033[0m] Switch task as incomplete/complete" << endl;
    cout << "[\033[0;93m4\033[0m] Delete Tasks" << endl;
    cout << "[\033[0;93m5\033[0m] Show Statistics" << endl;
    cout << "[\033[0;93m6\033[0m] Show history entries with statistics: " << (HISTORY_SHOWN ? "\033[0;92mVisible\033[0m\n" : "\033[0;91mHidden\033[0m\n");
    cout << "[\033[0;93m7\033[0m] Save tasks and history as JSON" << endl;
    cout << "[\033[0;93m8\033[0m] Timestamp format: " << (TIMESTAMP_RESOLVE ? "\033[0;92m%d-%m-%YYYY %H:%M:%S\033[0m\n" : "\033[0;93mEpoch-time\033[0m\n");
    cout << "[\033[0;93m0\033[0m] Exit" << endl;
    cout << endl;
    cout << "Select: ";
}

int main() {
	const char* home = getenv("HOME");

	if (home == nullptr) {
		cerr << "Cannot find HOME directory!\n";
		return 1;
	}

	string mainpath = string(home) + "/.local/share/taskman/";

	filesystem::create_directories(mainpath);
    vector<Task> tasks;
    vector<Status> history;
    history = readHistory(mainpath);
    tasks = readTasks(history, mainpath);
    bool HISTORY_SHOWN = false;
    bool TIMESTAMP_RESOLVE = true;

    int command = -1;
    uint64_t todel_id = 0;
    uint64_t tocomplete_id = 0;
    uint64_t nextTaskId;

    ifstream input (mainpath + "nextid.txt");
    if (!(input >> nextTaskId)) {
        nextTaskId = 0;
    }
    input.close();

    string description;

    for (const Task& task : tasks) {
        if (task.id >= nextTaskId) {
            nextTaskId = task.id + 1;
        }
    }

    ofstream output(mainpath + "nextid.txt");
    if (!output) {
        cerr << "Could not open nextid.txt\n";;
    } else
    {
        output << nextTaskId;
        output.close();
    }

    while (command != 0) {
        print_screen(HISTORY_SHOWN, TIMESTAMP_RESOLVE);

        if (!(cin >> command)) {
            if (cin.eof()) {
                cout << "Input closed. Goodbye!\n";
                break;
            }
            cin.clear();
            cin.ignore(numeric_limits<streamsize>::max(), '\n');
            cout << "Invalid input!\n";
            continue;
        }
        switch (command) {
        case 1:
            cout << "Give description: ";
            cin.ignore(numeric_limits<streamsize>::max(), '\n');
            getline(cin, description);
            if (description.empty() || description.find('|') != string::npos) {
                cerr << "Invalid description!\n";
                continue;
            }
            addTask(tasks, description, history, nextTaskId, mainpath);
            saveTasks(tasks, history, mainpath);
            continue;
        case 2:
            tasks = readTasks(history, mainpath);
            listTasks(tasks, history, TIMESTAMP_RESOLVE, mainpath);
            continue;
        case 3:
            cout << "Which task to complete?" << endl;
            if (!(cin >> tocomplete_id)) {
                if (cin.eof()) {
                    cout << "Input closed. Goodbye!\n";
                    break;
                }
                cin.clear();
                cin.ignore(numeric_limits<streamsize>::max(), '\n');
                cout << "Invalid input!\n";
                continue;
            }
            if (completeTask(tasks, tocomplete_id, history, mainpath)) {
                cout << "Task completed!\n";
            } else {
                cout << "Task not found!\n";
            }
            continue;
        case 4:
            cout << "Which task to delete?" << endl;
            if (!(cin >> todel_id)) {
                if (cin.eof()) {
                    cout << "Input closed. Goodbye!\n";
                    break;
                }
                cin.clear();
                cin.ignore(numeric_limits<streamsize>::max(), '\n');
                cout << "Invalid input!\n";
                continue;
            }

            if (deleteTask(tasks, todel_id, history, mainpath)) {
                cout << "Task deleted!\n";
            } else {
                cout << "Task not found!\n";
            }
            continue;
        case 5:
            showStatistics(tasks, history, HISTORY_SHOWN, TIMESTAMP_RESOLVE);
            continue;
        case 6:
            if (HISTORY_SHOWN)
            {
                HISTORY_SHOWN = false;
            } else {
                HISTORY_SHOWN = true;
            }
            continue;
        case 7:
            if (saveJSON_history(history, mainpath) &&
            saveJSON_tasks(tasks, nextTaskId, mainpath)) {
                cout << "JSON saved!\n";
            } else {
                cout << "JSON export failed!\n";
            }
            continue;
        case 8:
            if (TIMESTAMP_RESOLVE)
            {
                TIMESTAMP_RESOLVE = false;
            } else
            {
                TIMESTAMP_RESOLVE = true;
            }
            continue;
        case 0:
            break;
        default:
            cout << "Invalid command!\n";
            continue;

        }
        return 0;
    }
}
