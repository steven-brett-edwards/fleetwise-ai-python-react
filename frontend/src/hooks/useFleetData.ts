import { useQuery } from '@tanstack/react-query'
import { getFleetSummary, getVehicles, type VehicleFilters } from '../api/vehicles'
import { getOverdueMaintenance, getUpcomingMaintenance } from '../api/maintenance'

export function useFleetSummary() {
  return useQuery({ queryKey: ['fleet-summary'], queryFn: getFleetSummary })
}

export function useVehicles(filters: VehicleFilters) {
  return useQuery({
    queryKey: ['vehicles', filters],
    queryFn: () => getVehicles(filters),
  })
}

export function useOverdueMaintenance() {
  return useQuery({ queryKey: ['maintenance', 'overdue'], queryFn: getOverdueMaintenance })
}

export function useUpcomingMaintenance() {
  return useQuery({
    queryKey: ['maintenance', 'upcoming'],
    queryFn: () => getUpcomingMaintenance(30, 5000),
  })
}
