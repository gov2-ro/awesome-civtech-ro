using System.Collections.Generic;

namespace VotRomania.Models
{
    public class PollingStationModel
    {
        public int Id { get; set; }
        public double Latitude { get; set; }
        public double Longitude { get; set; }
        public string County { get; set; }
        public string Locality { get; set; }
        public string PollingStationNumber { get; set; }
        public string Institution { get; set; }
        public string Address { get; set; }
        public IEnumerable<AssignedAddresses> AssignedAddresses { get; set; }
    }

    public class AssignedAddresses
    {
        public int Id { get; set; }
        public int PollingStationId { get; set; }
        public string Locality { get; set; }
        public string StreetCode { get; set; }
        public string Street { get; set; }
        public string HouseNumbers { get; set; }
        public string Remarks { get; set; }
    }
}