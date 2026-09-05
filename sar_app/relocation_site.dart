class RelocationSite {
  final String name;
  final String type;
  final int capacity;
  final int currentPopulation;
  final double distance;
  final double elevation;
  final double suitability;
  final String access;
  final String safety;

  const RelocationSite({
    required this.name,
    required this.type,
    required this.capacity,
    required this.currentPopulation,
    required this.distance,
    required this.elevation,
    required this.suitability,
    required this.access,
    required this.safety,
  });

  int get remainingCapacity => capacity - currentPopulation;

  double get utilization =>
      capacity == 0 ? 0 : currentPopulation / capacity;
}