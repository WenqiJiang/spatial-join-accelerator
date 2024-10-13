#include "Tree_generation.hpp"

int main(int argc, char *argv[])
{
  printf("Running R-tree index construction & 4 parallel sync traversal\n");

  FILE *trace_file;
  char *file_name_1;
  char *file_name_2;

  // simple argument parsing, not checking types, order matters
  // ./Tree-generation trace_file max_entries fill_factor
  if (argc < 4)
  {
    printf("Not enough arguments! Usage: ./Tree-generation trace_1 trace_2 max_entries fill_factor(optional)\n");
    return 1;
  }
  else if (argc == 4)
  {
    file_name_1 = argv[1];
    file_name_2 = argv[2];
    max_entries = atoi(argv[3]);
  }
  else if (argc == 5)
  {
    file_name_1 = argv[1];
    file_name_2 = argv[2];
    max_entries = atoi(argv[3]);
    fill_factor = atof(argv[4]);
  }
  else
  {
    printf("Too many command line arguments! Usage: ./Tree-generation trace_1 trace_2 max_entries(optional) omp_threads(optional) fill_factor(optional)\n");
    return 1;
  }
  timespec start, end;

  // Read file 1
  trace_file = fopen(file_name_1, "r");
  fseek(trace_file, 0, SEEK_END);
  long long size = ftell(trace_file);
  fseek(trace_file, 0, SEEK_SET);

  // Check system memory
  struct sysinfo mem_info;
  if (sysinfo(&mem_info) != 0)
  {
    printf("Error: could not get system memory info.\n");
    return 1;
  }

  long long free_mem = mem_info.freeram * mem_info.mem_unit;
  if (free_mem < size)
  {
    printf("Error: not enough free memory to allocate buffer.\n");
    return 1;
  }

  char *file_buffer_1 = new char[size];
  setbuf(trace_file, file_buffer_1);

  // Parsing trace 1
  int num_rows, read;
  read = fscanf(trace_file, "%d\n", &num_rows);

  // MBR data per line
  MBR *mbr;
  float lowest0 = std::numeric_limits<float>::max();
  float highest0 = std::numeric_limits<float>::lowest();
  float lowest1 = std::numeric_limits<float>::max();
  float highest1 = std::numeric_limits<float>::lowest();
  for (int i = 0; i < num_rows; i++)
  {
    int id;
    float low0, high0, low1, high1;
    read = fscanf(trace_file, "%d %f %f %f %f\n", 
				&id, &low0, &high0, &low1, &high1);

    if(low0 < lowest0) lowest0 = low0;
    if(high0 > highest0) highest0 = high0;
    if(low1 < lowest1) lowest1 = low1;
    if(high1 > highest1) highest1 = high1;

    mbr = new MBR(low0, high0, low1, high1); // currently only does square MBRs (what they did in VLDB'14 with non-updating indices)
    agents.push_back(mbr);
    Event *eventBottom = new Event(low1, true, mbr, 0);
    Event *eventTop = new Event(high1, false, mbr, 0);
    sweep_data.push_back(eventBottom);
    sweep_data.push_back(eventTop);
  }
  mbr = new MBR(lowest0, highest0, lowest1, highest1);
  float l = lowest0;
  float r = highest0;

  // STR bulk-loading 1
  clock_gettime(CLOCK_BOOTTIME, &start);
  bulk_load(&agents, 0, mbr);
  clock_gettime(CLOCK_BOOTTIME, &end);

  timespec total_time = diff(start, end);
  float total_time_ms =
      ((float)total_time.tv_sec) * 1000.0 +
      ((float)total_time.tv_nsec) / 1000.0 / 1000.0;
  printf("Building RTree for trace 1: %.2f ms\n", total_time_ms);

  // Fixing tree 1
//   fix_tree(root_A);
  //index_serialization(root_A, "tree_A.bin");

  // Read file 2
  trace_file = fopen(file_name_2, "r");
  fseek(trace_file, 0, SEEK_END);
  size = ftell(trace_file);
  fseek(trace_file, 0, SEEK_SET);

  // Check system memory
  if (sysinfo(&mem_info) != 0)
  {
    printf("Error: could not get system memory info.\n");
    return 1;
  }

  free_mem = mem_info.freeram * mem_info.mem_unit;
  if (free_mem < size)
  {
    printf("Error: not enough free memory to allocate buffer.\n");
    return 1;
  }

  char *file_buffer_2 = new char[size];
  setbuf(trace_file, file_buffer_2);

  // Parsing trace 2
  read = fscanf(trace_file, "%d\n", &num_rows);

  // MBR data per line
  agents.clear();
  lowest0 = std::numeric_limits<float>::max();
  highest0 = std::numeric_limits<float>::lowest();
  lowest1 = std::numeric_limits<float>::max();
  highest1 = std::numeric_limits<float>::lowest();
  for (int i = 0; i < num_rows; i++)
  {
    int id;
    float low0, high0, low1, high1;
    read = fscanf(trace_file, "%d %f %f %f %f\n", 
				&id, &low0, &high0, &low1, &high1);

    if(low0 < lowest0) lowest0 = low0;
    if(low0 < l) l = low0;
    if(high0 > highest0) highest0 = high0;
    if(high0 > r) r = high0;
    if(low1 < lowest1) lowest1 = low1;
    if(high1 > highest1) highest1 = high1;

    mbr = new MBR(low0, high0, low1, high1); // currently only does square MBRs (what they did in VLDB'14 with non-updating indices)
    agents.push_back(mbr);
    Event *eventBottom = new Event(low1, true, mbr, 1);
    Event *eventTop = new Event(high1, false, mbr, 1);
    sweep_data.push_back(eventBottom);
    sweep_data.push_back(eventTop);
  }
  mbr = new MBR(lowest0, highest0, lowest1, highest1);

  // Free unused memory
  fclose(trace_file);
  delete[] file_buffer_1;

  // STR bulk-loading 2
  clock_gettime(CLOCK_BOOTTIME, &start);
  bulk_load(&agents, 1, mbr);
  clock_gettime(CLOCK_BOOTTIME, &end);

  total_time = diff(start, end);
  total_time_ms =
      ((float)total_time.tv_sec) * 1000.0 +
      ((float)total_time.tv_nsec) / 1000.0 / 1000.0;
  printf("Building RTree for trace 2: %.2f ms\n", total_time_ms);
  // Fixing tree 2
//   fix_tree(root_B);
  //index_serialization(root_B, "tree_B.bin");

  std::vector<std::pair<int, int>> new_results;
  clock_gettime(CLOCK_BOOTTIME, &start);
  sync_traversal(new_results, root_A, root_B);
  clock_gettime(CLOCK_BOOTTIME, &end);

  total_time = diff(start, end);
  total_time_ms =
      ((float)total_time.tv_sec) * 1000.0 +
      ((float)total_time.tv_nsec) / 1000.0 / 1000.0;
  printf("Sync traversal duration: %.2f ms\n", total_time_ms);
  printf("Number of results: %lu\n", new_results.size());

  // Perform sweep line join
  std::vector<std::pair<MBR *, MBR *>> sweep_results;
  clock_gettime(CLOCK_BOOTTIME, &start);
  sweep_line_join(sweep_results, &sweep_data, l);
  clock_gettime(CLOCK_BOOTTIME, &end);

  total_time = diff(start, end);
  total_time_ms =
      ((float)total_time.tv_sec) * 1000.0 +
      ((float)total_time.tv_nsec) / 1000.0 / 1000.0;
  printf("Sweep line join time: %.2f ms\n", total_time_ms);
  printf("Number of results: %lu\n", sweep_results.size());

  return 0;
}