import { useQuery } from '@tanstack/react-query'
import {
  getFleetSummary,
  getVehicleById,
  getVehicleMaintenance,
  getVehicleWorkOrders,
  getVehicles,
  type VehicleFilters,
} from '../api/vehicles'
import { getOverdueMaintenance, getUpcomingMaintenance } from '../api/maintenance'
import { getWorkOrderById, getWorkOrders, type WorkOrderFilters } from '../api/workOrders'

export function useFleetSummary() {
  return useQuery({ queryKey: ['fleet-summary'], queryFn: getFleetSummary })
}

export function useVehicles(filters: VehicleFilters) {
  return useQuery({
    queryKey: ['vehicles', filters],
    queryFn: () => getVehicles(filters),
  })
}

export function useVehicle(id: number | null) {
  return useQuery({
    queryKey: ['vehicle', id],
    queryFn: () => getVehicleById(id as number),
    enabled: id !== null && Number.isFinite(id),
  })
}

export function useVehicleMaintenance(id: number | null) {
  return useQuery({
    queryKey: ['vehicle', id, 'maintenance'],
    queryFn: () => getVehicleMaintenance(id as number),
    enabled: id !== null && Number.isFinite(id),
  })
}

export function useVehicleWorkOrders(id: number | null) {
  return useQuery({
    queryKey: ['vehicle', id, 'work-orders'],
    queryFn: () => getVehicleWorkOrders(id as number),
    enabled: id !== null && Number.isFinite(id),
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

export function useWorkOrders(filters: WorkOrderFilters) {
  return useQuery({
    queryKey: ['work-orders', filters],
    queryFn: () => getWorkOrders(filters),
  })
}

export function useWorkOrder(id: number | null) {
  return useQuery({
    queryKey: ['work-order', id],
    queryFn: () => getWorkOrderById(id as number),
    enabled: id !== null && Number.isFinite(id),
  })
}
