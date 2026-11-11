// SPDX-License-Identifier: AGPL-3.0-only
#include "local_geometry.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <new>
using namespace sonar::local;
namespace {
bool prohibit_allocations = false;
int failures = 0;
constexpr double pi = 3.14159265358979323846;
constexpr double tolerance = 1e-9; // Artificial double fixture, not sensor accuracy.
#define CHECK(expr) do { if (!(expr)) { std::fprintf(stderr, "%s:%d: %s\n", __func__, __LINE__, #expr); ++failures; } } while (false)
bool near(double a, double b) { return std::abs(a-b) <= tolerance; }
struct Fixture {
    Calibration c{};
    GeometryProfile g{1, 2000000, 2000000, 10000, 10000, 2000000, 20*pi/180, -10, 10, tolerance};
    RiskProfile r{1, Stage::fixture, 0.5, 2.5, 0.5, 0};
    ToFFrame f{};
    Orientation o{1, 1, 1000000, OrientationQuality::usable, {1,0,0,0}};
    FixtureAssociation a{};
    State state{};
    Time now{1000000};
    Fixture() {
        c.id=1; c.distance_kind=DistanceKind::radial;
        c.tof_to_head={{{1,0,0},{0,1,0},{0,0,1}}};
        f.boot_session=1; f.calibration_id=1; f.acquisition_id=1;
        f.captured_at_us=now; f.distance_kind=DistanceKind::radial;
        for (std::size_t i=0; i<64; ++i) { c.unit_rays[i]={1,0,0}; f.zones[i].index=static_cast<std::uint8_t>(i); }
    }
    void point(std::size_t i, double range, Vec3 ray={1,0,0}) {
        c.unit_rays[i]=ray; f.zones[i].quality=ZoneQuality::usable; f.zones[i].radial_range_m=range;
    }
    void advance(Time dt, double range) {
        now+=dt; f.captured_at_us=now; o.captured_at_us=now; ++f.acquisition_id;
        f.zones[0].radial_range_m=range;
    }
    void associate(std::uint8_t current=0, std::uint8_t previous=0) {
        a.source=AssociationSource::controlled_fixture_same_point;
        a.previous_acquisition_id=f.acquisition_id-1; a.count=1; a.links[0]={current,previous,1};
    }
    Result run(bool risk=true, bool association=false, bool frame=true, bool imu=true) {
        Input in{f.boot_session, now, frame?&f:nullptr, imu?&o:nullptr, &c, &g, risk?&r:nullptr, association?&a:nullptr};
        prohibit_allocations=true;
        auto result=update(in,state);
        prohibit_allocations=false;
        for (const auto& s:result.sectors) {
            for (const auto& v : {s.nearest_observed_range_m, s.closing_rate_m_s, s.radial_ttc_candidate_s, s.time_to_protection_s})
                CHECK(!v || std::isfinite(*v));
            CHECK(s.coverage.frame_usable+s.coverage.frame_invalid==64);
        }
        return result;
    }
};
void unavailable(const Result& r) {
    for (auto& s:r.sectors) { CHECK(s.assessment==Assessment::unavailable); CHECK(!s.nearest_observed_range_m); CHECK(!s.radial_ttc_candidate_s); CHECK(s.reasons!=0); }
}
void ac1() {
    Fixture f;
    const double h=std::sqrt(0.5);
    f.point(0,1,{h,h,0}); f.point(1,1); f.point(2,1,{h,-h,0});
    auto r=f.run(); for (auto& s:r.sectors) CHECK(s.coverage.projected_in_sector==1);
    for (double angle : {f.g.center_half_angle_rad,-f.g.center_half_angle_rad}) {
        Fixture b; b.point(0,1,{std::cos(angle),std::sin(angle),0});
        CHECK(b.run().sectors[1].source_zone==0);
        for (double offset : {-1e-8,1e-8}) {
            Fixture e; e.point(0,1,{std::cos(angle+offset),std::sin(angle+offset),0});
            auto sector=(angle+offset>e.g.center_half_angle_rad)?0:((angle+offset < -e.g.center_half_angle_rad)?2:1);
            CHECK(e.run().sectors[sector].source_zone==0);
        }
    }
}
void ac2() {
    Fixture f; f.point(0,2,{std::sqrt(3.0)/2,0,0.5}); f.g.z_min_m=-tolerance; f.g.z_max_m=tolerance;
    f.o.head_to_reference_wxyz={std::cos(pi/12),0,std::sin(pi/12),0};
    auto positive=f.run(); CHECK(positive.sectors[1].source_zone==0); CHECK(near(*positive.sectors[1].nearest_observed_range_m,2));
    for(auto& q:f.o.head_to_reference_wxyz) q=-q;
    auto negative=f.run(); CHECK(negative.sectors[1].source_zone==positive.sectors[1].source_zone);
    CHECK(negative.sectors[1].coverage.projected_in_sector==positive.sectors[1].coverage.projected_in_sector);
    // Probe the expected x=2 with ToF->head translation, then the same rotation.
    for(double displacement:{-1e-7,1e-7}) {
        Fixture boundary; boundary.point(0,2,{std::sqrt(3.0)/2,0,0.5});
        boundary.o.head_to_reference_wxyz={std::cos(pi/12),0,std::sin(pi/12),0};
        boundary.c.translation_tof_to_head={(-2+displacement)*std::sqrt(3.0)/2,0,(-2+displacement)*0.5};
        CHECK(boundary.run().sectors[1].source_zone.has_value()==(displacement>0));
    }
}
void ac3() {
    Fixture f; f.point(0,1); unavailable(f.run(true,false,true,false));
    for (auto quality:{OrientationQuality::missing,OrientationQuality::unreliable}) { f.o.quality=quality; unavailable(f.run()); }
    f.o.quality=OrientationQuality::usable;
    for(double q:{0.0,2.0,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()}) {
        f.o.head_to_reference_wxyz={q,0,0,0}; unavailable(f.run());
    }
}
void ac4() { Fixture f; unavailable(f.run(true,false,false)); unavailable(f.run()); }
void ac5() {
    Fixture f; f.point(0,0.25); auto s=f.run().sectors[1];
    CHECK(s.coverage.frame_usable==1); CHECK(s.coverage.frame_invalid==63); CHECK(s.coverage.projected_in_sector==1);
    CHECK(s.assessment==Assessment::limited); CHECK(s.observed_band==Band::urgent); CHECK(near(*s.nearest_observed_range_m,0.25));
}
void ac6() {
    for(Time age:{99000ULL,100000ULL,101000ULL}) {
        Fixture f; f.point(0,1); f.g.max_tof_age_us=100000; f.g.max_imu_age_us=100000; f.now+=age;
        auto r=f.run(); if(age==99000) CHECK(r.sectors[1].source_zone==0); else { unavailable(r); CHECK(has(r.sectors[1].reasons,Reason::stale)); }
    }
    for(Time skew:{10000ULL,11000ULL}) {
        Fixture f; f.point(0,1); f.now+=skew; f.o.captured_at_us+=skew;
        auto r=f.run(); if(skew==10000) CHECK(r.sectors[1].source_zone==0); else { unavailable(r); CHECK(has(r.sectors[1].reasons,Reason::skew)); }
    }
    Fixture f; f.point(0,1); ++f.f.captured_at_us; unavailable(f.run());
    Fixture old_imu; old_imu.point(0,1); old_imu.g.max_imu_age_us=100000;
    old_imu.o.captured_at_us-=100000; old_imu.g.max_skew_us=100000;
    unavailable(old_imu.run());
    Fixture future_imu; future_imu.point(0,1); ++future_imu.o.captured_at_us; unavailable(future_imu.run());
}
void ac7() {
    Fixture f; f.point(0,3); CHECK(!f.run().sectors[1].closing_rate_m_s);
    f.f.zones[0].radial_range_m=10; f.associate(); auto duplicate=f.run(true,true);
    CHECK(!duplicate.sectors[1].closing_rate_m_s); CHECK(has(duplicate.sectors[1].reasons,Reason::duplicate));
    CHECK(near(*f.state.ranges[0],3));
    f.advance(1000000,2); f.associate(); CHECK(near(*f.run(true,true).sectors[1].closing_rate_m_s,1));
    f.now-=1; f.f.captured_at_us=f.now; f.o.captured_at_us=f.now; ++f.f.acquisition_id; f.associate();
    auto reg=f.run(true,true); CHECK(!reg.sectors[1].closing_rate_m_s); CHECK(has(reg.sectors[1].reasons,Reason::clock_regression));
    CHECK(!f.state.has_history);
    Fixture timestamp; timestamp.point(0,3); timestamp.run(); ++timestamp.f.acquisition_id; --timestamp.f.captured_at_us;
    timestamp.associate(); CHECK(!timestamp.run(true,true).sectors[1].closing_rate_m_s); CHECK(!timestamp.state.has_history);
    Fixture loss; loss.point(0,3); loss.run(); loss.run(true,false,false);
    loss.advance(1000000,2); loss.associate(); CHECK(!loss.run(true,true).sectors[1].closing_rate_m_s);
}
void ac8() {
    for(Time dt:{9000ULL,10000ULL,100000ULL,101000ULL}) {
        Fixture f; f.g.dt_max_us=100000; f.point(0,3); f.run(); f.advance(dt,2); f.associate(); auto s=f.run(true,true).sectors[1];
        CHECK(s.nearest_observed_range_m.has_value()); CHECK(s.closing_rate_m_s.has_value()==(dt==10000 || dt==100000));
    }
}
void ac9() {
    Fixture f; f.point(0,3); f.run(); f.advance(1000000,2); f.associate(); auto s=f.run(true,true).sectors[1];
    CHECK(s.motion_basis==MotionBasis::controlled_fixture); CHECK(s.closing_rate_m_s && near(*s.closing_rate_m_s,1));
    CHECK(s.radial_ttc_candidate_s && near(*s.radial_ttc_candidate_s,2)); CHECK(s.time_to_protection_s && near(*s.time_to_protection_s,1.5));
    Fixture p; p.point(0,1); p.run(); p.advance(1000000,0.25); p.associate(); CHECK(p.run(true,true).sectors[1].time_to_protection_s==0);
}
void ac10() {
    for(double range:{3.0,4.0}) { Fixture f; f.point(0,3); f.run(); f.advance(1000000,range); f.associate(); auto s=f.run(true,true).sectors[1];
        CHECK(s.closing_rate_m_s && *s.closing_rate_m_s<=0); CHECK(!s.radial_ttc_candidate_s); CHECK(has(s.reasons,Reason::not_closing)); }
    Fixture f; f.r.min_closing_rate_m_s=1; f.point(0,3); f.run(); f.advance(1000000,2); f.associate(); CHECK(!f.run(true,true).sectors[1].radial_ttc_candidate_s);
}
void ac11() {
    Fixture f; f.point(0,3); f.point(1,4); f.run(); f.advance(1000000,2);
    CHECK(!f.run().sectors[1].closing_rate_m_s);
    Fixture other; other.point(0,3); other.point(1,4); other.run(); other.advance(1000000,2); other.associate(1,1);
    CHECK(!other.run(true,true).sectors[1].closing_rate_m_s);
    Fixture cross_zone; cross_zone.point(0,3); cross_zone.point(1,4); cross_zone.run();
    cross_zone.advance(1000000,2); cross_zone.associate(0,1);
    auto linked=cross_zone.run(true,true).sectors[1]; CHECK(linked.closing_rate_m_s && near(*linked.closing_rate_m_s,2));
    for(int bad=0;bad<5;++bad) {
        Fixture e; e.point(0,3); e.run(); e.advance(1000000,2); e.associate();
        if(bad==0) e.a.previous_acquisition_id=99;
        if(bad==1) e.a.links[0].point_id=0;
        if(bad==2) { e.a.count=2; e.a.links[1]=e.a.links[0]; }
        if(bad==3) e.a.count=65;
        if(bad==4) e.a.source=AssociationSource::unknown;
        CHECK(!e.run(true,true).sectors[1].closing_rate_m_s);
    }
}
void ac12() {
    for(int change=0;change<8;++change) {
        Fixture f; f.point(0,3); f.run(); f.advance(1000000,2); f.associate();
        if(change==0) { f.f.boot_session=2; f.o.boot_session=2; }
        if(change==1) f.o.reference_id=2;
        if(change==2) { f.c.id=2; f.f.calibration_id=2; }
        if(change==3) f.g.id=2;
        if(change==4) f.r.id=2;
        if(change==5) f.r.attention_range_m=4;
        if(change==6) f.g.z_max_m=11;
        if(change==7) f.c.translation_tof_to_head.x=0.1;
        auto s=f.run(true,true).sectors[1]; CHECK(s.source_zone==0); CHECK(!s.closing_rate_m_s); CHECK(has(s.reasons,Reason::continuity_reset));
    }
    Fixture f; f.point(0,1); f.f.calibration_id=2; unavailable(f.run());
    f.f.calibration_id=1; f.o.boot_session=2; unavailable(f.run());
    f.o.boot_session=1; Input in{2,f.now,&f.f,&f.o,&f.c,&f.g,&f.r,nullptr}; unavailable(update(in,f.state));
}
void ac13() {
    for(int bad=0;bad<5;++bad) {
        Fixture f; f.point(0,1);
        if(bad==1) f.r.urgent_range_m=std::numeric_limits<double>::quiet_NaN();
        if(bad==2) f.r.urgent_range_m=f.r.attention_range_m;
        if(bad==3) f.r.stage=Stage::unapproved;
        if(bad==4) f.r.id=0;
        auto s=f.run(bad!=0).sectors[1]; CHECK(s.assessment==Assessment::unconfigured); CHECK(s.nearest_observed_range_m==1); CHECK(!s.observed_band); CHECK(!s.radial_ttc_candidate_s);
    }
}
void ac14() {
    Fixture a,b; a.point(0,1); b.point(0,1);
    // No camera/network/VM input exists; both calls execute offline under allocation guard.
    auto x=a.run(), y=b.run();
    CHECK(x.boot_session==y.boot_session); CHECK(x.captured_at_us==y.captured_at_us);
    for(std::size_t i=0;i<3;++i) { CHECK(x.sectors[i].assessment==y.sectors[i].assessment); CHECK(x.sectors[i].reasons==y.sectors[i].reasons); CHECK(x.sectors[i].nearest_observed_range_m==y.sectors[i].nearest_observed_range_m); }
}
void ac15() {
    for(double bad:{0.0,-1.0,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()}) {
        Fixture f; f.point(0,bad); unavailable(f.run());
    }
    Fixture missing; missing.point(0,1); missing.f.zones[0].radial_range_m.reset(); unavailable(missing.run());
    Fixture duplicate; duplicate.point(0,1); duplicate.f.zones[1].index=0; unavailable(duplicate.run());
    duplicate.f.zones[1].index=64; unavailable(duplicate.run());
    Fixture reordered; reordered.point(0,1); std::swap(reordered.f.zones[0],reordered.f.zones[63]); CHECK(reordered.run().sectors[1].source_zone==0);
    Fixture full; for(std::size_t i=0;i<64;++i) full.point(i,1); auto all=full.run().sectors[1]; CHECK(all.assessment==Assessment::known); CHECK(all.coverage.projected_in_sector==64);
    Fixture badray; badray.point(0,1,{2,0,0}); unavailable(badray.run());
    Fixture axial; axial.point(0,1); axial.f.distance_kind=DistanceKind::axial; unavailable(axial.run());
    Fixture rotation; rotation.point(0,1); rotation.c.tof_to_head[0][0]=-1; unavailable(rotation.run());
    Fixture config; config.point(0,1); config.g.unit_norm_tolerance=0; unavailable(config.run());
    Fixture extreme; extreme.point(0,std::numeric_limits<double>::max()); extreme.c.translation_tof_to_head.x=std::numeric_limits<double>::max(); unavailable(extreme.run());
    Fixture rate; rate.point(0,std::numeric_limits<double>::max()); rate.run(); rate.advance(10000,1); rate.associate(); CHECK(!rate.run(true,true).sectors[1].closing_rate_m_s);
    Fixture partial_ray; partial_ray.point(0,0.25); partial_ray.point(1,1,{2,0,0});
    auto partial=partial_ray.run().sectors[1]; CHECK(partial.observed_band==Band::urgent); CHECK(partial.coverage.frame_usable==1);
    Fixture max_clock; max_clock.point(0,3); max_clock.now=std::numeric_limits<Time>::max()-1000000;
    max_clock.f.captured_at_us=max_clock.now; max_clock.o.captured_at_us=max_clock.now;
    max_clock.run(); max_clock.advance(1000000,2); max_clock.associate();
    auto high=max_clock.run(true,true).sectors[1]; CHECK(high.closing_rate_m_s && near(*high.closing_rate_m_s,1));
    CHECK(std::tuple_size<decltype(State{}.ranges)>::value<=128); // Spec bounds history records, not ESP RAM.
}
void ac16() {
    for(Vec3 ray:{Vec3{-1,0,0},Vec3{0,1,0},Vec3{0.6,0,0.8}}) {
        Fixture f; f.g.z_min_m=-0.5; f.g.z_max_m=0.5; f.point(0,1,ray); auto r=f.run(); unavailable(r); CHECK(has(r.sectors[1].reasons,Reason::excluded));
    }
    Fixture head; head.point(0,1); head.run(); head.o.head_to_reference_wxyz={0,0,1,0}; unavailable(head.run());
    Fixture height; height.g.z_min_m=0; height.g.z_max_m=0; height.point(0,1); CHECK(height.run().sectors[1].source_zone==0);
}
}
void* operator new(std::size_t n) {
    if(prohibit_allocations) { std::fputs("Allocation during update\n",stderr); std::abort(); }
    if(void* p=std::malloc(n?n:1)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n) { return ::operator new(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
#if defined(__cpp_sized_deallocation)
void operator delete(void* p,std::size_t) noexcept { std::free(p); }
void operator delete[](void* p,std::size_t) noexcept { std::free(p); }
#endif
int main() {
    const std::array<void(*)(),16> tests{ac1,ac2,ac3,ac4,ac5,ac6,ac7,ac8,ac9,ac10,ac11,ac12,ac13,ac14,ac15,ac16};
    for(std::size_t i=0;i<tests.size();++i) { auto before=failures; tests[i](); std::printf("AC-%zu: %s\n",i+1,failures==before?"PASS":"FAIL"); }
    std::printf("16 acceptance groups; failures=%d; State=%zu bytes (native)\n",failures,sizeof(State));
    return failures?1:0;
}
