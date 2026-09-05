class CapacityData {
  final String name;
  final int population;
  final int capacity;
  final double waterPerDay;
  final double foodPerDay;
  final int shelterUnits;
  final String medicalPriority;

  const CapacityData({
    required this.name,
    required this.population,
    required this.capacity,
    required this.waterPerDay,
    required this.foodPerDay,
    required this.shelterUnits,
    required this.medicalPriority,
  });

  int get remaining => capacity - population;

  double get utilization =>
      capacity == 0 ? 0 : population / capacity;
}