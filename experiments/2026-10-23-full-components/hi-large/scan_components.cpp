#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

using Clock = std::chrono::steady_clock;
using Id = uint32_t;
using Count = uint64_t;
constexpr std::string_view HEADER = "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering";

struct Node { Id parent, size, first; Count rows; };
struct Component { Id first, size; Count rows; };

std::string json(std::string_view value) {
    std::string result = "\"";
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { result += '\\'; result += c; }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += c;
    }
    return result + '"';
}

std::array<std::string_view, 11> fields(const std::string &line) {
    if (line.find('"') != std::string::npos) throw std::runtime_error("quoted CSV is unsupported");
    std::array<std::string_view, 11> result;
    size_t begin = 0;
    for (size_t i = 0; i < result.size(); ++i) {
        size_t end = line.find(',', begin);
        if ((i == 10) != (end == std::string::npos)) throw std::runtime_error("expected exactly 11 CSV fields");
        if (end == std::string::npos) end = line.size();
        result[i] = std::string_view(line).substr(begin, end - begin);
        begin = end + 1;
    }
    return result;
}

std::string key(std::string_view bank, std::string_view account) {
    if (bank.empty() || bank.find_first_not_of("0123456789") != std::string_view::npos)
        throw std::runtime_error("bank must be a nonempty unsigned decimal string");
    if (account.empty()) throw std::runtime_error("account must not be empty");
    if (account.find('\0') != std::string_view::npos) throw std::runtime_error("NUL in account is unsupported");
    size_t first = bank.find_first_not_of('0');
    bank.remove_prefix(first == std::string_view::npos ? bank.size() - 1 : first);
    std::string result(bank);
    result += '\0';
    result += account;
    return result;
}

void validate_timestamp(std::string_view value) {
    if (value.size() != 16) throw std::runtime_error("expected timestamp YYYY/MM/DD HH:MM");
    for (size_t i = 0; i < value.size(); ++i) {
        char separator = i == 4 || i == 7 ? '/' : i == 10 ? ' ' : i == 13 ? ':' : 0;
        if (separator ? value[i] != separator : value[i] < '0' || value[i] > '9')
            throw std::runtime_error("expected timestamp YYYY/MM/DD HH:MM");
    }
}

class Graph {
public:
    std::unordered_map<std::string, Id> ids;
    std::vector<std::string> keys;
    std::vector<Node> nodes;

    Id node(std::string value) {
        auto found = ids.find(value);
        if (found != ids.end()) return found->second;
        if (nodes.size() >= std::numeric_limits<Id>::max()) throw std::runtime_error("32-bit node-ID capacity exceeded");
        Id id = static_cast<Id>(nodes.size());
        ids.emplace(value, id);
        keys.push_back(std::move(value));
        nodes.push_back({id, 1, id, 0});
        return id;
    }

    Id root(Id id) {
        while (nodes[id].parent != id) {
            nodes[id].parent = nodes[nodes[id].parent].parent;
            id = nodes[id].parent;
        }
        return id;
    }

    void edge(Id from, Id to) {
        Id a = root(from), b = root(to);
        if (a != b) {
            if (nodes[a].size < nodes[b].size) std::swap(a, b);
            nodes[b].parent = a;
            nodes[a].size += nodes[b].size;
            nodes[a].rows += nodes[b].rows;
            nodes[a].first = std::min(nodes[a].first, nodes[b].first);
        }
        ++nodes[a].rows;
    }

    std::pair<std::string_view, std::string_view> representative(Id first) const {
        std::string_view value(keys[first]);
        size_t split = value.find('\0');
        return {value.substr(0, split), value.substr(split + 1)};
    }
};

void histogram(std::ostream &out, const std::map<Count, Count> &counts) {
    out << '[';
    bool comma = false;
    for (auto [size, count] : counts) {
        if (comma) out << ',';
        out << "{\"size\":" << size << ",\"components\":" << count << '}';
        comma = true;
    }
    out << ']';
}

int main(int argc, char **argv) {
    Count line_number = 0;
    try {
        if (argc != 3) throw std::runtime_error("usage: scan_components INPUT.csv OUTPUT_PREFIX");
        const auto start = Clock::now();
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open input");
        std::string line, min_timestamp, max_timestamp;
        if (!std::getline(input, line)) throw std::runtime_error("missing header");
        ++line_number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.compare(0, 3, "\xEF\xBB\xBF") == 0) line.erase(0, 3);
        if (line != HEADER) throw std::runtime_error("unexpected CSV header");
        Graph graph;
        graph.ids.reserve(1 << 20);
        Count transactions = 0, self_rows = 0;
        while (std::getline(input, line)) {
            ++line_number;
            if (!line.empty() && line.back() == '\r') line.pop_back();
            auto f = fields(line);
            validate_timestamp(f[0]);
            if (transactions == 0 || f[0] < min_timestamp) min_timestamp = f[0];
            if (transactions == 0 || f[0] > max_timestamp) max_timestamp = f[0];
            Id from = graph.node(key(f[1], f[2]));
            Id to = graph.node(key(f[3], f[4]));
            graph.edge(from, to);
            self_rows += from == to;
            ++transactions;
            if (transactions % 10000000 == 0)
                std::cerr << "rows=" << transactions << " accounts=" << graph.nodes.size() << " elapsed_seconds="
                          << std::chrono::duration<double>(Clock::now() - start).count() << '\n';
        }
        if (!input.eof()) throw std::runtime_error("input read failed");
        const double scan_seconds = std::chrono::duration<double>(Clock::now() - start).count();
        std::vector<Component> components;
        std::map<Count, Count> account_histogram, row_histogram;
        Count sum_accounts = 0, sum_rows = 0;
        for (size_t id = 0; id < graph.nodes.size(); ++id) {
            const auto &node = graph.nodes[id];
            if (node.parent != id) continue;
            components.push_back({node.first, node.size, node.rows});
            ++account_histogram[node.size];
            ++row_histogram[node.rows];
            sum_accounts += node.size;
            sum_rows += node.rows;
        }
        if (sum_accounts != graph.nodes.size() || sum_rows != transactions)
            throw std::runtime_error("component totals do not match scanned totals");
        std::sort(components.begin(), components.end(), [](auto a, auto b) { return a.first < b.first; });
        std::ofstream inventory(std::string(argv[2]) + ".components.csv");
        if (!inventory) throw std::runtime_error("cannot create component inventory");
        inventory << "component_id,representative_bank,representative_account,accounts,transactions\n";
        for (auto component : components) {
            auto [bank, account] = graph.representative(component.first);
            inventory << component.first << ',' << bank << ',' << account << ',' << component.size << ',' << component.rows << '\n';
        }
        inventory.close();
        if (!inventory) throw std::runtime_error("component inventory write failed");
        auto ranked = components;
        std::partial_sort(ranked.begin(), ranked.begin() + std::min<size_t>(20, ranked.size()), ranked.end(), [](auto a, auto b) {
            if (a.rows != b.rows) return a.rows > b.rows;
            if (a.size != b.size) return a.size > b.size;
            return a.first < b.first;
        });
        std::ofstream output(std::string(argv[2]) + ".summary.json");
        if (!output) throw std::runtime_error("cannot create summary");
        output << std::setprecision(12)
               << "{\n  \"input\": " << json(argv[1])
               << ",\n  \"transactions\": " << transactions << ",\n  \"accounts\": " << graph.nodes.size()
               << ",\n  \"components\": " << components.size() << ",\n  \"self_rows\": " << self_rows
               << ",\n  \"min_timestamp\": " << (transactions ? json(min_timestamp) : "null")
               << ",\n  \"max_timestamp\": " << (transactions ? json(max_timestamp) : "null")
               << ",\n  \"scan_seconds\": " << scan_seconds
               << ",\n  \"component_id_definition\": \"Smallest zero-based source-first appearance node ordinal in each component\""
               << ",\n  \"totals_verified\": true,\n  \"largest_components_by_transactions\": [";
        for (size_t i = 0; i < std::min<size_t>(20, ranked.size()); ++i) {
            auto c = ranked[i];
            auto [bank, account] = graph.representative(c.first);
            if (i) output << ',';
            output << "{\"component_id\":" << c.first << ",\"representative_bank\":" << json(bank)
                   << ",\"representative_account\":" << json(account) << ",\"accounts\":" << c.size
                   << ",\"transactions\":" << c.rows << '}';
        }
        output << "],\n  \"component_account_size_histogram\": ";
        histogram(output, account_histogram);
        output << ",\n  \"component_transaction_size_histogram\": ";
        histogram(output, row_histogram);
        output << "\n}\n";
        output.close();
        if (!output) throw std::runtime_error("summary write failed");
        std::cerr << "complete rows=" << transactions << " accounts=" << graph.nodes.size()
                  << " components=" << components.size() << " elapsed_seconds="
                  << std::chrono::duration<double>(Clock::now() - start).count() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "error at input line " << line_number << ": " << error.what() << '\n';
        return 1;
    }
}
